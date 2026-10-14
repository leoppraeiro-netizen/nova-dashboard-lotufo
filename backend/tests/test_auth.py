from app import db, auth

def _conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn(); db.migrate(conn); return conn

def test_criar_e_autenticar(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-forte-123")["nome"] == "Leo"
    assert auth.autenticar(conn, "leo@lotufo.com", "errada") is None

def test_lockout_apos_5_falhas(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    for _ in range(5):
        auth.autenticar(conn, "leo@lotufo.com", "errada")
    # mesmo com senha certa, bloqueado
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-forte-123") is None

def test_sessao(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    uid = auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    token, csrf = auth.criar_sessao(conn, uid)
    s = auth.sessao_valida(conn, token)
    assert s["usuario_id"] == uid and s["csrf_token"] == csrf
    assert auth.sessao_valida(conn, "token-invalido") is None

def test_login_endpoint(client):
    # seed via app (usa o mesmo banco do client)
    r = client.post("/api/auth/login", json={"email": "x@x.com", "senha": "y"})
    assert r.status_code == 401


# --- testes adicionais (nao previstos no brief) -------------------------------

def _seed(email="leo@lotufo.com", senha="senha-forte-123", perfil="admin"):
    conn = db.get_conn()
    db.migrate(conn)
    uid = auth.criar_usuario(conn, "Leo", email, senha, perfil)
    conn.close()
    return uid

def _login(client, email="leo@lotufo.com", senha="senha-forte-123"):
    r = client.post("/api/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200, r.text
    # cookie secure nao volta sozinho em http://testserver: injetar na jar do client
    token = r.cookies.get("sessao") or client.cookies.get("sessao")
    client.cookies.set("sessao", token)
    return r.json(), token

def test_fluxo_login_eu_logout(client):
    _seed()
    corpo, token = _login(client)
    assert corpo["nome"] == "Leo" and corpo["perfil"] == "admin" and corpo["csrf"]
    assert corpo["email"] == "leo@lotufo.com"      # gate Sol S6 (10/10/2026): login e /eu dizem o e-mail

    r = client.get("/api/auth/eu")
    assert r.status_code == 200
    assert r.json()["email"] == "leo@lotufo.com"
    assert "senha_hash" not in r.json()
    # /eu devolve o csrf da sessao: e assim que o front o recupera depois de um F5
    assert r.json()["csrf"] == corpo["csrf"]

    r = client.post("/api/auth/logout")
    assert r.status_code == 200
    client.cookies.set("sessao", token)  # cookie continua no cliente, sessao morreu
    assert client.get("/api/auth/eu").status_code == 401

def test_csrf_de_eu_serve_para_mutacao(client_admin):
    # simula o F5: o front perdeu o token (so vive em memoria) e o recupera pelo /eu
    del client_admin.headers["X-CSRF-Token"]
    assert client_admin.post("/api/rm/sincronizar").status_code == 403
    client_admin.headers["X-CSRF-Token"] = client_admin.get("/api/auth/eu").json()["csrf"]
    # passou pelo CSRF; 422 = RM nao configurado neste servidor de teste
    assert client_admin.post("/api/rm/sincronizar").status_code == 422

def test_eu_sem_cookie_401(client):
    assert client.get("/api/auth/eu").status_code == 401

def test_cookie_login_e_httponly_e_samesite(client):
    _seed()
    r = client.post("/api/auth/login", json={"email": "leo@lotufo.com", "senha": "senha-forte-123"})
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=strict" in set_cookie
    assert "secure" in set_cookie
    # o token do cookie nao e o que esta gravado no banco (guardamos o hash)
    token = r.cookies.get("sessao") or client.cookies.get("sessao")
    conn = db.get_conn()
    assert conn.execute("SELECT 1 FROM sessoes WHERE token_hash=?", (token,)).fetchone() is None
    assert auth.sessao_valida(conn, token) is not None
    conn.close()

def test_sessao_expirada(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    uid = auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    token, _ = auth.criar_sessao(conn, uid)
    conn.execute("UPDATE sessoes SET expira_em='2000-01-01T00:00:00+00:00'")
    conn.commit()
    assert auth.sessao_valida(conn, token) is None

def test_encerrar_sessao(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    uid = auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    token, _ = auth.criar_sessao(conn, uid)
    auth.encerrar_sessao(conn, token)
    assert auth.sessao_valida(conn, token) is None

def test_login_zera_tentativas(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    for _ in range(3):
        auth.autenticar(conn, "leo@lotufo.com", "errada")
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-forte-123") is not None
    row = conn.execute("SELECT tentativas_falhas, bloqueado_ate FROM usuarios").fetchone()
    assert row["tentativas_falhas"] == 0 and row["bloqueado_ate"] is None

def test_usuario_inativo_nao_autentica(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    conn.execute("UPDATE usuarios SET ativo=0")
    conn.commit()
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-forte-123") is None

def test_email_case_insensitive(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "LEO@Lotufo.com", "senha-forte-123", "admin")
    assert auth.autenticar(conn, "leo@LOTUFO.com", "senha-forte-123") is not None

def test_senha_nao_fica_em_texto_claro(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    h = conn.execute("SELECT senha_hash FROM usuarios").fetchone()["senha_hash"]
    assert "senha-forte-123" not in h
    assert h.startswith("$argon2")

def test_sessao_de_usuario_desativado_nao_vale(client):
    # revisao round 1, IMPORTANT 1: desativar o usuario tem que matar a sessao viva
    _seed()
    _login(client)
    assert client.get("/api/auth/eu").status_code == 200

    conn = db.get_conn()
    conn.execute("UPDATE usuarios SET ativo=0")
    conn.commit()
    conn.close()

    assert client.get("/api/auth/eu").status_code == 401

def test_autenticar_email_inexistente(tmp_path, monkeypatch):
    # revisao round 1, IMPORTANT 2: com o verify dummy no caminho, o retorno segue None
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    assert auth.autenticar(conn, "ninguem@lotufo.com", "senha-forte-123") is None
    assert auth.autenticar(conn, "ninguem@lotufo.com", "qualquer") is None

def test_autenticar_bloqueado_retorna_none(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    conn.execute("UPDATE usuarios SET bloqueado_ate=?",
                 ((auth._agora() + auth.timedelta(minutes=10)).isoformat(),))
    conn.commit()
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-forte-123") is None

def test_exigir_csrf(client):
    from fastapi import Depends
    from app.api_auth import exigir_csrf
    _seed()
    corpo, _ = _login(client)

    @client.app.post("/api/_teste_csrf")
    def _protegido(usuario: dict = Depends(exigir_csrf)):
        return {"ok": True}

    assert client.post("/api/_teste_csrf").status_code == 403
    assert client.post("/api/_teste_csrf", headers={"X-CSRF-Token": "errado"}).status_code == 403
    r = client.post("/api/_teste_csrf", headers={"X-CSRF-Token": corpo["csrf"]})
    assert r.status_code == 200

def test_login_recusa_email_longo_demais(client):
    # A tentativa falha grava o e-mail digitado no log de auditoria, que e' append-only:
    # sem teto de tamanho, uma string arbitrariamente grande incha o log de graca.
    # 254 e' o limite pratico de um endereco de e-mail (RFC), entao nada legitimo cai aqui.
    r = client.post("/api/auth/login", json={"email": "a" * 300, "senha": "y"})
    assert r.status_code == 422

def test_autenticar_hash_corrompido_retorna_none(tmp_path, monkeypatch):
    # senha_hash corrompido levanta InvalidHashError: nao pode virar 500, tem que
    # retornar None e NAO incrementar o contador (e problema de dado, nao senha errada).
    conn = _conn(tmp_path, monkeypatch)
    uid = auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    conn.execute("UPDATE usuarios SET senha_hash='lixo-nao-argon2' WHERE id=?", (uid,))
    conn.commit()
    assert auth.autenticar(conn, "leo@lotufo.com", "qualquer-senha") is None
    assert conn.execute("SELECT tentativas_falhas FROM usuarios WHERE id=?", (uid,)).fetchone()["tentativas_falhas"] == 0


def test_cookie_sem_secure_com_DASH_SEM_TLS(client, monkeypatch):
    # producao HTTP na rede interna: sem "Secure" o navegador aceita o cookie em http://
    from app import auth, db
    conn = db.get_conn()
    auth.criar_usuario(conn, "U", "u@l.com", "senha-forte-123", "engenharia")
    conn.close()
    monkeypatch.setenv("DASH_SEM_TLS", "1")
    r = client.post("/api/auth/login", json={"email": "u@l.com", "senha": "senha-forte-123"})
    assert r.status_code == 200
    assert "secure" not in r.headers["set-cookie"].lower()
    assert "httponly" in r.headers["set-cookie"].lower()


# --- A-06 (testes de quebra 10/10/2026): contador de senhas erradas atomico ---------------

def test_dez_falhas_em_paralelo_bloqueiam_a_conta(tmp_path, monkeypatch):
    # Antes: cada tentativa lia `tentativas_falhas` fora da transacao e gravava "lido + 1";
    # 10 tentativas simultaneas gravavam 1 e o bloqueio nunca chegava (a senha certa entrava).
    import threading
    conn = _conn(tmp_path, monkeypatch)
    uid = auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    largada = threading.Barrier(10)

    def tentar():
        c = db.get_conn()
        try:
            largada.wait()
            auth.autenticar(c, "leo@lotufo.com", "errada")
        finally:
            c.close()

    threads = [threading.Thread(target=tentar) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    row = conn.execute("SELECT bloqueado_ate FROM usuarios WHERE id=?", (uid,)).fetchone()
    assert row["bloqueado_ate"] is not None
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-forte-123") is None
    # bloqueio vencido (gravado no passado): a senha certa volta a entrar
    conn.execute("UPDATE usuarios SET bloqueado_ate=? WHERE id=?",
                 ((auth._agora() - auth.timedelta(minutes=1)).isoformat(), uid))
    conn.commit()
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-forte-123") is not None


# --- A-10 (testes de quebra 10/10/2026): texto do campo e-mail na auditoria ---------------

def _ultima_falha():
    import json
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT depois FROM audit_log WHERE acao='auth.login_falha' ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    return json.loads(row["depois"])

def test_login_falho_com_texto_que_nao_e_email_nao_grava_o_texto(client):
    # quem cola a senha no campo e-mail deixava a senha no log append-only
    r = client.post("/api/auth/login", json={"email": "minha frase secreta 123", "senha": "x"})
    assert r.status_code == 401
    depois = _ultima_falha()
    assert "minha frase secreta 123" not in str(depois)
    # gate Sol S6: so' a faixa do tamanho, nao o numero exato de caracteres
    assert depois == {"email": None, "motivo": "texto inválido no campo e-mail", "faixa": "17-32"}

def test_login_falho_com_senha_que_parece_email_sem_dominio_nao_grava(client):
    # gate Sol S3: "Senha@2026" passava pelo padrao (um "@" e sem espaco) e ia a' auditoria
    for texto, faixa in (("Senha@2026", "1-16"), ("x" * 40 + "@algo", ">32")):
        assert client.post("/api/auth/login", json={"email": texto, "senha": "x"}).status_code == 401
        assert _ultima_falha() == {"email": None, "motivo": "texto inválido no campo e-mail", "faixa": faixa}

def test_login_falho_com_email_grava_o_email(client):
    r = client.post("/api/auth/login", json={"email": "Fulano@Exemplo.com", "senha": "x"})
    assert r.status_code == 401
    assert _ultima_falha() == {"email": "fulano@exemplo.com"}


# --- Gate Sol S1 (10/10/2026): troca de senha nao desfaz a redefinicao concorrente do admin -----

def test_trocar_senha_nao_sobrescreve_redefinicao_concorrente(tmp_path, monkeypatch):
    import pytest
    conn = _conn(tmp_path, monkeypatch)
    uid = auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "engenharia")
    token, _ = auth.criar_sessao(conn, uid)
    real = auth._ph

    class _AdminNoMeio:
        """Enquanto o Argon2 da troca roda, o admin redefine a senha por outra conexao."""
        disparou = False
        def hash(self, senha):
            if not self.disparou and senha == "senha-do-atacante":
                self.disparou = True
                outra = db.get_conn()
                try:
                    auth.redefinir_senha(outra, None, uid, "senha-do-admin-99")
                finally:
                    outra.close()
            return real.hash(senha)
        def __getattr__(self, nome):
            return getattr(real, nome)

    monkeypatch.setattr(auth, "_ph", _AdminNoMeio())
    with pytest.raises(ValueError):
        auth.trocar_senha(conn, uid, "senha-forte-123", "senha-do-atacante", token)
    monkeypatch.setattr(auth, "_ph", real)
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-do-atacante") is None
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-do-admin-99") is not None


# --- #4: canal de tempo no login ------------------------------------------------------------
# Conta existente com senha errada roda um verify argon2 E grava o contador (BEGIN IMMEDIATE e
# commit com pagina alterada, que custa a escrita no WAL). "E-mail inexistente" e "conta
# bloqueada" tem que pagar o mesmo par de custos, senao o tempo entrega quais e-mails tem conta.

def _custo(conn, monkeypatch, email, senha):
    """Conta os verify argon2, as transacoes de escrita e se alguma pagina foi gravada."""
    contagem = {"verify": 0}
    real = auth._ph

    class _Contador:
        def verify(self, h, s):
            contagem["verify"] += 1
            return real.verify(h, s)
        def __getattr__(self, nome):
            return getattr(real, nome)

    monkeypatch.setattr(auth, "_ph", _Contador())
    sql = []
    conn.set_trace_callback(sql.append)
    antes = conn.total_changes
    try:
        assert auth.autenticar(conn, email, senha) is None
    finally:
        conn.set_trace_callback(None)
        monkeypatch.setattr(auth, "_ph", real)
    return {"verify": contagem["verify"],
            "begin_immediate": sum(1 for s in sql if s.strip().upper().startswith("BEGIN IMMEDIATE")),
            "escreveu": conn.total_changes > antes}

def _usuarios(conn):
    return [tuple(r) for r in conn.execute("SELECT * FROM usuarios ORDER BY id")]

def test_login_inexistente_custa_o_mesmo_que_senha_errada(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    existente = _custo(conn, monkeypatch, "leo@lotufo.com", "errada")
    assert existente == {"verify": 1, "begin_immediate": 1, "escreveu": True}
    antes = _usuarios(conn)
    assert _custo(conn, monkeypatch, "ninguem@lotufo.com", "errada") == existente
    # a escrita equivalente nao deixa rastro: nenhum dado de usuario muda
    assert _usuarios(conn) == antes

def test_login_bloqueado_custa_o_mesmo_que_senha_errada(tmp_path, monkeypatch):
    # igualado o inexistente ao existente, o bloqueado (que nao gravava) viraria o caminho distinguivel
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    auth.criar_usuario(conn, "Ana", "ana@lotufo.com", "senha-forte-456", "engenharia")
    conn.execute("UPDATE usuarios SET bloqueado_ate=? WHERE email='ana@lotufo.com'",
                 ((auth._agora() + auth.timedelta(minutes=10)).isoformat(),))
    conn.commit()
    existente = _custo(conn, monkeypatch, "leo@lotufo.com", "errada")
    antes = _usuarios(conn)
    assert _custo(conn, monkeypatch, "ana@lotufo.com", "senha-forte-456") == existente
    assert _usuarios(conn) == antes
