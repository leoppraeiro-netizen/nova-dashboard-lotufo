from app import auth, db


def test_contas_microsoft_lista_quem_conectou(client_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_GRAPH_TOKENS_DIR", str(tmp_path / "tokens"))
    conn = db.get_conn()
    maria = auth.criar_usuario(conn, "Maria", "maria@lotufo.com", "senha-forte-123", "engenharia")
    conn.close()
    (tmp_path / "tokens").mkdir()
    (tmp_path / "tokens" / f"usuario-{maria}.txt").write_text("refresh-token", encoding="utf-8")

    r = client_admin.get("/api/admin/contas-microsoft")
    assert r.status_code == 200, r.text
    por_email = {c["email"]: c for c in r.json()}
    assert por_email["maria@lotufo.com"]["conectada"] is True
    assert por_email["maria@lotufo.com"]["token_em"]
    assert por_email["admin@lotufo.com"] == {**por_email["admin@lotufo.com"], "conectada": False, "token_em": None}


def _gravar_eventos(n):
    from app import auditoria
    conn = db.get_conn()
    with db.mutacao(conn):
        for i in range(n):
            auditoria.registrar(conn, None, f"teste.evento{i}")
    conn.close()


def test_auditoria_cursor_devolve_todos_os_eventos_sem_repetir(client_admin):
    # 600 eventos (mais os do login do admin): duas chamadas com cursor percorrem tudo, ate' o primeiro
    _gravar_eventos(600)
    conn = db.get_conn()
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()
    p1 =client_admin.get("/api/admin/auditoria", params={"limite": 500}).json()
    assert len(p1["eventos"]) == 500 and p1["ha_mais"] is True
    p2 = client_admin.get("/api/admin/auditoria",
                          params={"limite": 500, "antes_de": p1["eventos"][-1]["id"]}).json()
    ids = [e["id"] for e in p1["eventos"] + p2["eventos"]]
    assert len(ids) == total == len(set(ids))
    assert p2["ha_mais"] is False
    assert p2["eventos"][-1]["id"] == 1
    # a cadeia inteira e' verificada so' na primeira pagina; as seguintes nao repetem o custo
    assert p1["cadeia_integra"] is True and p2["cadeia_integra"] is None


def test_auditoria_ha_mais_falso_quando_a_pagina_pega_o_ultimo(client_admin):
    conn = db.get_conn()
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()
    r = client_admin.get("/api/admin/auditoria", params={"limite": total}).json()
    assert len(r["eventos"]) == total and r["ha_mais"] is False


def test_auditoria_cursor_invalido_e_422_nao_500(client_admin):
    for cursor in (0, -1, 2 ** 63):
        assert client_admin.get("/api/admin/auditoria", params={"antes_de": cursor}).status_code == 422


def test_auditoria_traz_a_obra_da_medicao_e_do_protocolo(client_admin):
    from app import auditoria
    from tests.conftest import novo_contrato
    cid = novo_contrato({"orgao": "SINFRA", "numero_instrumento": "IC 1/2026", "objeto": "Obra",
                         "valor_original": "100.000,00"})
    mid = client_admin.post(f"/api/contratos/{cid}/medicoes",
                            json={"numero": 1, "tipo": "execucao", "competencia": "2026-07"}).json()["id"]
    conn = db.get_conn()
    with db.mutacao(conn):
        pid = conn.execute("INSERT INTO protocolos (contrato_id, etapa, natureza, usuario_id) VALUES (?,?,?,1)",
                           (cid, "unico", "execucao")).lastrowid
        auditoria.registrar(conn, None, "protocolo.criar", "protocolo", pid)
        auditoria.registrar(conn, None, "medicao.protocolo", "medicao", 99999)  # medicao que nao existe mais
    conn.close()
    por_acao = {e["acao"]: e for e in client_admin.get("/api/admin/auditoria").json()["eventos"]}
    assert mid and por_acao["medicao.criar"]["contrato_id"] == cid
    assert por_acao["protocolo.criar"]["contrato_id"] == cid
    assert por_acao["medicao.protocolo"]["contrato_id"] is None
    assert por_acao["auth.login"]["contrato_id"] is None
