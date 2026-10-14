from tests.conftest import novo_contrato

NOVO = {"orgao": "SINFRA-MT", "numero_instrumento": "IC 082/2025",
        "objeto": "MT-388", "valor_original": "1.000.000,00",
        "vigencia_fim": "2027-12-31", "execucao_fim": "2027-06-30"}

def test_listar(client_admin):
    cid = novo_contrato(NOVO)
    lista = client_admin.get("/api/contratos").json()
    assert any(c["id"] == cid and c["valor_vigente_centavos"] == 100_000_000 for c in lista)

def test_sem_login_nega(client):
    assert client.get("/api/contratos").status_code == 401

def test_detalhe_inexistente_404(client_admin):
    assert client_admin.get("/api/contratos/9999").status_code == 404

def test_perfil_diretoria_le(client):
    from app import auth, db
    conn = db.get_conn()
    auth.criar_usuario(conn, "Dir", "dir@lotufo.com", "senha-forte-123", "diretoria")
    conn.close()
    r = client.post("/api/auth/login", json={"email": "dir@lotufo.com", "senha": "senha-forte-123"})
    client.cookies.set("sessao", r.cookies.get("sessao") or client.cookies.get("sessao"))
    assert client.get("/api/contratos").status_code == 200

def test_escrita_de_contrato_pela_api_saiu(client_admin):
    """Bloco 9: contrato entra pelo cadastro versionado (`cadastro aplicar`), nao pela tela."""
    cid = novo_contrato(NOVO)
    assert client_admin.post("/api/contratos", json=NOVO).status_code == 405
    assert client_admin.put(f"/api/contratos/{cid}", json=NOVO).status_code == 405
    assert client_admin.post(f"/api/contratos/{cid}/estado",
                             json={"estado": "suspenso", "data": "2026-08-01"}).status_code == 404
