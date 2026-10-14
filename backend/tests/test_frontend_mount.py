"""O mount do build React em "/" nao pode engolir a API.

Este teste roda com DASH_SEM_FRONTEND DESLIGADO (ao contrario da fixture `client`),
com um dist temporario, para fixar a ordem: routers primeiro, mount depois.
"""
from fastapi.testclient import TestClient

from app.main import create_app

INDEX = "<!doctype html><html><head><title>Dashboard Lotufo</title></head><body><div id=\"root\"></div></body></html>"

def _app_com_dist(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DASH_SEM_JOBS", "1")
    monkeypatch.delenv("DASH_SEM_FRONTEND", raising=False)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX, encoding="utf-8")
    monkeypatch.setenv("DASH_DIST_PATH", str(dist))
    return create_app()

def test_api_vence_o_mount_e_raiz_serve_o_index(tmp_path, monkeypatch):
    with TestClient(_app_com_dist(tmp_path, monkeypatch)) as c:
        saude = c.get("/api/health")
        assert saude.status_code == 200
        assert saude.json()["status"] == "ok"

        raiz = c.get("/")
        assert raiz.status_code == 200
        assert "Dashboard Lotufo" in raiz.text
        assert raiz.headers["content-type"].startswith("text/html")

def test_caminho_desconhecido_continua_404(tmp_path, monkeypatch):
    # html=True serve o index so em caminho de diretorio ("/"): /api/* inexistente
    # continua 404 (nao vira index.html).
    with TestClient(_app_com_dist(tmp_path, monkeypatch)) as c:
        assert c.get("/api/nao-existe").status_code == 404

def test_caminho_de_tela_serve_o_index(tmp_path, monkeypatch):
    # Fase 3,5: o frontend tem URL por tela. F5 em "/contratos/7/protocolo" tem que
    # devolver o index (o roteador do React resolve o caminho); arquivo com extensao
    # inexistente continua 404 -- um index no lugar de um .js quebraria a pagina.
    with TestClient(_app_com_dist(tmp_path, monkeypatch)) as c:
        for caminho in ("/painel", "/contratos/7", "/contratos/7/protocolo", "/certidoes"):
            r = c.get(caminho)
            assert r.status_code == 200, caminho
            assert "Dashboard Lotufo" in r.text
        assert c.get("/assets/nao-existe.js").status_code == 404
        assert c.get("/api/nao-existe").status_code == 404
        assert c.get("/api").status_code == 404   # o namespace inteiro, inclusive a raiz dele
