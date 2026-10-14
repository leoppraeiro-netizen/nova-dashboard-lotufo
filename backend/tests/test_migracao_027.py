"""Migracao 027: tabelas da deteccao arquivadas (renomeadas), nada apagado."""
from app import db
import pytest

# Exercita a propria migracao: parte de um banco vazio de verdade, sem o banco-modelo do
# conftest (issue #88).
pytestmark = pytest.mark.migracao_real

TABELAS = ("sugestoes", "deteccao_padroes", "deteccao_config", "mensagens_observadas", "planilhas_config",
           "planilhas_observadas", "graph_sincronizacoes")


def _tabelas(c) -> set[str]:
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_027_renomeia_e_preserva(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn()
    db.migrate(c)
    assert not set(TABELAS) & _tabelas(c)
    assert {f"arquivo_{t}" for t in TABELAS} <= _tabelas(c)
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    db.migrate(c)                                          # reexecucao
    c.close()


def test_027_leva_as_linhas_para_o_arquivo(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn()
    # banco "ate' a 026": a 027 marcada como aplicada nao roda; depois desmarca e migra de novo
    c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (nome TEXT PRIMARY KEY)")
    c.execute("INSERT INTO schema_migrations (nome) VALUES ('027_corte.sql')"); c.commit()
    db.migrate(c)
    c.execute("INSERT INTO sugestoes (tipo, payload) VALUES ('nf_ambigua', '{}')")
    c.execute("INSERT INTO mensagens_observadas (mensagem_id, categoria, resultado) VALUES ('m1', 'protocolo', 'ruido')")
    c.execute("DELETE FROM schema_migrations WHERE nome='027_corte.sql'"); c.commit()
    db.migrate(c)
    assert c.execute("SELECT tipo FROM arquivo_sugestoes").fetchall()[0][0] == "nf_ambigua"
    assert c.execute("SELECT mensagem_id FROM arquivo_mensagens_observadas").fetchall()[0][0] == "m1"
    c.close()
