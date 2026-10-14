"""`python -m app.cli desbloquear|redefinir-senha <email>`: saida para o unico admin que se trancou (A-05, 10/10/2026)."""
from app import auth, cli, db


def _banco(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    uid = auth.criar_usuario(c, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    return c, uid


def test_desbloquear_pela_linha_de_comando(tmp_path, monkeypatch, capsys):
    c, uid = _banco(tmp_path, monkeypatch)
    for _ in range(5):
        auth.autenticar(c, "leo@lotufo.com", "errada")
    assert auth.autenticar(c, "leo@lotufo.com", "senha-forte-123") is None
    assert cli.main(["desbloquear", "LEO@lotufo.com"]) == 0
    assert "desbloqueado" in capsys.readouterr().out.lower()
    assert auth.autenticar(c, "leo@lotufo.com", "senha-forte-123") is not None
    assert c.execute("SELECT COUNT(*) FROM audit_log WHERE acao='usuario.desbloquear'").fetchone()[0] == 1
    c.close()


def test_redefinir_senha_pela_linha_de_comando(tmp_path, monkeypatch, capsys):
    c, uid = _banco(tmp_path, monkeypatch)
    token, _ = auth.criar_sessao(c, uid)
    monkeypatch.setattr(cli.getpass, "getpass", lambda *a, **k: "senha-nova-456")
    assert cli.main(["redefinir-senha", "leo@lotufo.com"]) == 0
    assert auth.sessao_valida(c, token) is None
    assert auth.autenticar(c, "leo@lotufo.com", "senha-nova-456") is not None
    c.close()


def test_email_desconhecido_ou_senha_curta_falham(tmp_path, monkeypatch, capsys):
    c, _ = _banco(tmp_path, monkeypatch)
    assert cli.main(["desbloquear", "ninguem@lotufo.com"]) == 1
    monkeypatch.setattr(cli.getpass, "getpass", lambda *a, **k: "curta")
    assert cli.main(["redefinir-senha", "leo@lotufo.com"]) == 1
    assert "10 caracteres" in capsys.readouterr().out
    assert auth.autenticar(c, "leo@lotufo.com", "senha-forte-123") is not None
    c.close()
