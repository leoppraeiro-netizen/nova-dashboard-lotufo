import pytest


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["status"] == "ok" and corpo["banco"] == "ok"
    assert "ultimo_snapshot" in corpo["backup"]


def test_health_503_quando_o_banco_nao_responde(client, monkeypatch):
    import sqlite3
    from app import db
    def quebrada():
        raise sqlite3.OperationalError("unable to open database file")
    monkeypatch.setattr(db, "get_conn", quebrada)
    r = client.get("/api/health")
    assert r.status_code == 503 and r.json()["status"] == "erro"


def test_logs_em_arquivo_quando_DASH_LOG_DIR(tmp_path, monkeypatch):
    import logging
    from app import logs
    monkeypatch.setenv("DASH_LOG_DIR", str(tmp_path / "logs"))
    arquivo = logs.configurar()
    logs.configurar()  # segunda chamada nao duplica handler
    try:
        logging.getLogger("uvicorn.error").info("subiu")
        logging.getLogger("app.backup").error("falhou")
        for h in logging.getLogger("uvicorn").handlers:
            h.flush()
        texto = arquivo.read_text(encoding="utf-8")
        assert texto.count("subiu") == 1 and "falhou" in texto
    finally:
        for nome in logs._LOGGERS:
            lg = logging.getLogger(nome)
            for h in [h for h in lg.handlers if h.get_name() == logs._NOME_HANDLER]:
                lg.removeHandler(h); h.close()
            if nome:
                lg.propagate = True


def test_app_sobe_sem_modulo_de_robo(tmp_path, monkeypatch):
    """Spec §15.2: o robo das federais saiu. Nenhum atributo dele pode sobrar no app."""
    import importlib
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "r.db"))
    monkeypatch.setenv("DASH_SEM_JOBS", "1")
    monkeypatch.setenv("DASH_SEM_FRONTEND", "1")
    import app.main as m
    importlib.reload(m)
    assert not hasattr(m, "robo_mod")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.robo_certidoes")
