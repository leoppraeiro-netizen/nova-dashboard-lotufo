import threading

import pytest
from app import api_correio, graph

_THREAD = threading.Thread          # a fixture troca threading.Thread pela parada; o teste do clique duplo usa a real


class _ThreadParada:
    """No lugar de threading.Thread: o acompanhamento do login nao roda no teste (ele dormiria
    5 s e acordaria DEPOIS do teste, ja' sem o monkeypatch, batendo na rede de verdade)."""
    def __init__(self, **_):
        pass

    def start(self):
        pass


@pytest.fixture(autouse=True)
def _ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_GRAPH_TOKENS_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("DASH_GRAPH_CLIENT_ID", "cliente-teste")
    monkeypatch.setattr(api_correio.threading, "Thread", _ThreadParada)
    api_correio._LOGINS.clear()          # estado de login e' global do processo: zera entre testes
    yield
    api_correio._LOGINS.clear()


def test_status_de_quem_nunca_conectou(client_admin):
    r = client_admin.get("/api/correio/status").json()
    assert r["configurado"] is True and r["conectado"] is False and r["login"]["estado"] == "nenhum"


def test_conectar_devolve_o_codigo_so_para_quem_pediu(client_admin, monkeypatch):
    monkeypatch.setattr(graph, "iniciar_device_code", lambda tenant, cid, escopos: {
        "device_code": "d", "user_code": "ABCD-1234", "verification_uri": "https://microsoft.com/devicelogin",
        "expires_in": 900, "interval": 5, "message": ""})
    r = client_admin.post("/api/correio/conectar").json()
    assert r["login"]["user_code"] == "ABCD-1234" and r["login"]["estado"] == "aguardando"


def test_conectar_de_novo_enquanto_aguarda_devolve_o_mesmo_codigo_sem_travar(client_admin, monkeypatch):
    # 14/10/2026: o segundo clique pegava a trava dentro da propria trava e o servidor parava de responder
    # o estado da conta para todo mundo, ate' reiniciar.
    pedidos = []
    monkeypatch.setattr(graph, "iniciar_device_code", lambda tenant, cid, escopos: pedidos.append(1) or {
        "device_code": "d", "user_code": "ABCD-1234", "verification_uri": "https://microsoft.com/devicelogin",
        "expires_in": 900, "interval": 5, "message": ""})
    client_admin.post("/api/correio/conectar")
    resposta = {}
    t = _THREAD(target=lambda: resposta.update(r=client_admin.post("/api/correio/conectar")), daemon=True)
    t.start()
    t.join(5)
    if t.is_alive():
        api_correio._LOCK.release()      # solta a trava presa para nao pendurar os outros testes
        pytest.fail("o segundo clique em Conectar travou o servidor")
    assert resposta["r"].status_code == 200 and resposta["r"].json()["login"]["user_code"] == "ABCD-1234"
    assert len(pedidos) == 1                                     # nao pede outro codigo a' Microsoft
    assert client_admin.get("/api/correio/status").json()["login"]["estado"] == "aguardando"


def test_teste_envia_para_a_propria_pessoa_e_registra(client_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_GRAPH_SIMULADOR", str(tmp_path / "sim"))
    r = client_admin.post("/api/correio/teste")
    assert r.status_code == 200, r.text
    assert r.json()["remetente"] == "admin@lotufo.com"
    assert sorted((tmp_path / "sim" / "enviados").glob("*.json"))[0].exists()


def test_teste_sem_conta_conectada_explica_o_que_fazer(client_admin):
    r = client_admin.post("/api/correio/teste")
    assert r.status_code == 422 and "Minha conta" in r.json()["detail"]


def test_diretoria_le_o_status_mas_nao_conecta(client):
    """B-09 (10/10/2026): /conta da diretoria lia "Permissao necessaria: editar_cadastros"; o status so' exige
    ver_paineis, as acoes seguem com editar_cadastros."""
    from app import auth, db
    conn = db.get_conn()
    auth.criar_usuario(conn, "Diretor", "dir@lotufo.com", "senha-forte-123", "diretoria")
    conn.close()
    r = client.post("/api/auth/login", json={"email": "dir@lotufo.com", "senha": "senha-forte-123"})
    client.cookies.set("sessao", r.cookies.get("sessao") or client.cookies.get("sessao"))
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    assert client.get("/api/correio/status").status_code == 200
    assert client.post("/api/correio/conectar").status_code == 403
    assert client.post("/api/correio/teste").status_code == 403


def test_assinatura_png_cortada_ao_meio_da_422_em_portugues(client_admin):
    """#33: o cabecalho PNG sozinho nao basta; arquivo truncado e' recusado e nada e' gravado."""
    from tests.conftest import _png
    png = _png()
    r = client_admin.post("/api/correio/assinatura", files={"arquivo": ("a.png", png[: len(png) // 2], "image/png")})
    assert r.status_code == 422 and "incompleta ou corrompida" in r.json()["detail"]
    assert client_admin.get("/api/correio/status").json()["assinatura"] is False
    r = client_admin.post("/api/correio/assinatura", files={"arquivo": ("a.png", png, "image/png")})
    assert r.status_code == 200 and r.json()["assinatura"] is True
