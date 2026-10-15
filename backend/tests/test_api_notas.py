"""Rotas da nota (bloco 3). O texto lido do PDF e' injetado por monkeypatch em
`notas.leitura_pdf.texto_de_pdf_com_limite` (mesma razao de test_notas.py: o PDF de mentira do conftest
nao devolve acentos); o PDF enviado e' valido para as guardas de upload."""
import pytest

from app import auth, db, notas
from tests.conftest import _pdf_com_texto, novo_contrato
from tests.test_api_espelhos import ambiente_api  # noqa: F401  (fixture: MT-402 ativa no banco do client)
from tests.test_notas import _nota_como

PDF = _pdf_com_texto("nota")


def _fixar_texto(monkeypatch, texto):
    monkeypatch.setattr(notas.leitura_pdf, "texto_de_pdf_com_limite", lambda pdf: texto)


@pytest.fixture
def medicao_qualquer(client_admin):
    cid = novo_contrato({"orgao": "SINFRA", "numero_instrumento": "IC 1/2026",
                                                    "objeto": "Obra", "valor_original": "100.000,00"})
    return client_admin.post(f"/api/contratos/{cid}/medicoes",
                             json={"numero": 1, "tipo": "execucao", "competencia": "2026-08"}).json()["id"]


@pytest.fixture
def client_diretoria(client):
    """So' `ver_paineis`: le, nao anexa."""
    conn = db.get_conn()
    auth.criar_usuario(conn, "Dir", "dir@lotufo.com", "senha-forte-123", "diretoria")
    conn.close()
    r = client.post("/api/auth/login", json={"email": "dir@lotufo.com", "senha": "senha-forte-123"})
    assert r.status_code == 200, r.text
    client.cookies.set("sessao", r.cookies.get("sessao") or client.cookies.get("sessao"))
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    return client


def test_anexar_nota_e_listar(client_admin, ambiente_api, monkeypatch):
    cid = ambiente_api
    r = client_admin.post(f"/api/contratos/{cid}/espelho", json={"numero": 27, "competencia": "2026-08",
                                                                  "entradas": {"medicao": "719.190,72"}})
    assert r.status_code == 201, r.text
    esp = client_admin.get(f"/api/espelhos/{r.json()['espelho_id']}").json()
    saida = next(s for s in esp["saidas"] if s["natureza"] == "medicao")
    mid = next(m["id"] for m in esp["medicoes"] if m["tipo"] == "execucao")
    antes = client_admin.get(f"/api/medicoes/{mid}/notas").json()
    assert antes["faltam"] == 1 and antes["esperadas"][0]["nota_id"] is None and antes["pode_declarar"]
    _fixar_texto(monkeypatch, _nota_como({**saida, "municipio": "Cuiabá"}, 3106))
    r = client_admin.post(f"/api/medicoes/{mid}/notas", files={"arquivo": ("3106.pdf", PDF, "application/pdf")})
    assert r.status_code == 201, r.text
    assert r.json()["leitura"]["ok"] and r.json()["faltam"] == 0 and r.json()["estado"] == "nota_emitida"
    r = client_admin.get(f"/api/medicoes/{mid}/notas")
    assert r.json()["esperadas"][0]["nota_id"] == r.json()["notas"][0]["nota_id"]
    assert r.json()["notas"][0]["confirmacao"] == "aguardando_rm" and r.json()["notas"][0]["conferencia"] == []
    assert r.json()["pode_declarar"] is False
    # o documento local baixa pela rota da medicao
    doc = next(d for d in client_admin.get(f"/api/medicoes/{mid}").json()["documentos"] if d["tipo_doc"] == "nfs")
    assert doc["numero_nf"] == "3106" and doc["fonte"] == "operacao"
    assert client_admin.get(f"/api/medicoes/{mid}/documentos/{doc['id']}").status_code == 200


def test_upload_que_nao_e_pdf_e_415(client_admin, medicao_qualquer):
    r = client_admin.post(f"/api/medicoes/{medicao_qualquer}/notas", files={"arquivo": ("x.pdf", b"nao e pdf", "application/pdf")})
    assert r.status_code == 415
    assert client_admin.post("/api/medicoes/99999/notas", files={"arquivo": ("x.pdf", PDF, "application/pdf")}).status_code == 404


def test_pdf_ilegivel_vira_documento_e_manual_valida_numero_e_valor(client_admin, medicao_qualquer, monkeypatch):
    _fixar_texto(monkeypatch, "")
    r = client_admin.post(f"/api/medicoes/{medicao_qualquer}/notas", files={"arquivo": ("scan.pdf", PDF, "application/pdf")})
    assert r.status_code == 201 and r.json()["nota_id"] is None and r.json()["leitura"]["motivo"] == "sem-texto"
    doc = r.json()["documento_id"]
    # o PDF sem nota continua listado para a pessoa informar os dados depois
    assert [d["documento_id"] for d in client_admin.get(f"/api/medicoes/{medicao_qualquer}/notas").json()["documentos_sem_nota"]] == [doc]
    r = client_admin.post(f"/api/medicoes/{medicao_qualquer}/notas/manual",
                          json={"documento_id": doc, "numero": 0, "emissao": "2026-09-14", "valor": "1,00"})
    assert r.status_code == 422
    r = client_admin.post(f"/api/medicoes/{medicao_qualquer}/notas/manual",
                          json={"documento_id": doc, "numero": 3106, "emissao": "2026-09-14", "valor": "719.190,72"})
    assert r.status_code == 200 and r.json()["nota_id"], r.text
    assert r.json()["conferencia"] == []       # medicao sem valor: nada a conferir
    assert client_admin.get(f"/api/medicoes/{medicao_qualquer}/notas").json()["documentos_sem_nota"] == []


def test_declarar_vincular_e_justificar(client_admin, ambiente_api, monkeypatch):
    cid = ambiente_api
    r = client_admin.post(f"/api/contratos/{cid}/espelho", json={"numero": 28, "competencia": "2026-09",
                                                                  "entradas": {"medicao": "1.000,00"}})
    esp = client_admin.get(f"/api/espelhos/{r.json()['espelho_id']}").json()
    mid = next(m["id"] for m in esp["medicoes"] if m["tipo"] == "execucao")
    # sem nota: declarar e' recusado
    assert client_admin.post(f"/api/medicoes/{mid}/notas/completa", json={"justificativa": "x"}).status_code == 422
    # o vinculo manual com NF do RM saiu: a rota nao existe mais e a lista nao vem na resposta
    assert "candidatas_rm" not in client_admin.get(f"/api/medicoes/{mid}/notas").json()
    assert client_admin.post(f"/api/medicoes/{mid}/notas/vincular", json={"nota_id": 1}).status_code in (404, 405)
    assert client_admin.post("/api/notas/99999/justificar", json={"justificativa": "ok"}).status_code == 422


def test_sem_permissao_nao_anexa(medicao_qualquer, client_diretoria):
    # ordem dos parametros = ordem de login: a medicao nasce com o admin, depois entra a diretoria
    r = client_diretoria.post(f"/api/medicoes/{medicao_qualquer}/notas", files={"arquivo": ("a.pdf", PDF, "application/pdf")})
    assert r.status_code == 403
    assert client_diretoria.get(f"/api/medicoes/{medicao_qualquer}/notas").status_code == 200


def test_sem_permissao_nao_libera_o_envio_sem_a_outra_metade(medicao_qualquer, client_diretoria):
    """Issue #188: a saida de emergencia e' de quem edita; quem so' consulta le as metades."""
    r = client_diretoria.post(f"/api/medicoes/{medicao_qualquer}/envio-sem-a-outra",
                              json={"justificativa": "notas do reajuste presas no faturamento"})
    assert r.status_code == 403
    assert client_diretoria.get(f"/api/medicoes/{medicao_qualquer}/par").json()["metades"] == []


def test_valor_acima_do_teto_da_422_na_nota_manual(client_admin, medicao_qualquer, monkeypatch):
    """A-08 (testes de quebra 10/10/2026): valor acima de int64 estourava o INSERT (500)."""
    _fixar_texto(monkeypatch, "")
    doc = client_admin.post(f"/api/medicoes/{medicao_qualquer}/notas",
                            files={"arquivo": ("scan.pdf", PDF, "application/pdf")}).json()["documento_id"]
    corpo = {"documento_id": doc, "numero": 3106, "emissao": "2026-09-14"}
    r = client_admin.post(f"/api/medicoes/{medicao_qualquer}/notas/manual", json={**corpo, "valor": "99999999999999999999,00"})
    assert r.status_code == 422 and "máximo aceito (R$ 99.999.999.999,99)" in r.json()["detail"]
    r = client_admin.post(f"/api/medicoes/{medicao_qualquer}/notas/manual", json={**corpo, "valor": "99.999.999.999,99"})
    assert r.status_code == 200, r.text


def test_protocolo_feito_fora_depois_da_nota_pelo_caminho_real(client_admin, ambiente_api, monkeypatch):
    """Gate Sol S4 (10/10/2026): sem fabricar estado por SQL -- espelho, nota anexada pela API, protocolo."""
    cid = ambiente_api
    r = client_admin.post(f"/api/contratos/{cid}/espelho", json={"numero": 29, "competencia": "2026-08",
                                                                  "entradas": {"medicao": "719.190,72"}})
    esp = client_admin.get(f"/api/espelhos/{r.json()['espelho_id']}").json()
    saida = next(s for s in esp["saidas"] if s["natureza"] == "medicao")
    mid = next(m["id"] for m in esp["medicoes"] if m["tipo"] == "execucao")
    assert client_admin.get(f"/api/medicoes/{mid}").json()["estado"] == "espelho_gerado"
    r = client_admin.post(f"/api/medicoes/{mid}/protocolo", json={"data": "2026-09-20"})
    assert r.status_code == 422 and "Nota fiscal ainda não emitida" in r.json()["detail"]
    _fixar_texto(monkeypatch, _nota_como({**saida, "municipio": "Cuiabá"}, 2290))
    r = client_admin.post(f"/api/medicoes/{mid}/notas", files={"arquivo": ("2290.pdf", PDF, "application/pdf")})
    assert r.status_code == 201 and r.json()["estado"] == "nota_emitida", r.text
    r = client_admin.post(f"/api/medicoes/{mid}/protocolo", json={"data": "2026-09-20"})
    assert r.status_code == 201 and r.json()["ressalva"] is None, r.text
    assert client_admin.get(f"/api/medicoes/{mid}").json()["estado"] == "protocolada"
