"""Migracao 022: `notas_fiscais.leitura` aceita 'danfse'; a reconstrucao preserva linhas e filhas."""
import sqlite3

import pytest

from app import db

# Exercita a propria migracao: parte de um banco vazio de verdade, sem o banco-modelo do
# conftest (issue #88).
pytestmark = pytest.mark.migracao_real


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    yield c
    c.close()


def test_leitura_danfse_aceita_e_valor_estranho_recusado(conn):
    conn.execute("INSERT INTO notas_fiscais (coligada, numero, numero_int, valor_centavos, origem, confirmacao, leitura) "
                 "VALUES (1, '3106', 3106, 100, 'pdf', 'aguardando_rm', 'danfse')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO notas_fiscais (coligada, numero, numero_int, valor_centavos, origem, confirmacao, leitura) "
                     "VALUES (1, '3207', 3207, 100, 'pdf', 'aguardando_rm', 'ocr')")


def test_reexecucao_preserva_notas_e_filhas(conn):
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos) VALUES ('S','X','o',100)")
    conn.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia, estado) VALUES (1, 1, 'execucao', '2026-08', 'protocolada')")
    conn.execute("INSERT INTO notas_fiscais (coligada, idmov, numero, numero_int, valor_centavos, leitura, valor_pdf_centavos) "
                 "VALUES (1, 5, '000003106', 3106, 100, 'danfse', 100)")
    conn.execute("INSERT INTO baixas (coligada, idlan, nota_id, valor_original_centavos, status_lan) VALUES (1, 9, 1, 100, 1)")
    conn.execute("INSERT INTO nf_alocacoes (medicao_id, nota_id, valor_alocado_centavos, origem) VALUES (1, 1, 100, 'manual')")
    conn.commit()
    sql = (db.MIGRATIONS_DIR / "022_leitura_danfse.sql").read_text(encoding="utf-8")
    conn.executescript(db._sem_alters_ja_aplicados(conn, sql))
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert tuple(conn.execute("SELECT idmov, numero_int, leitura, valor_pdf_centavos FROM notas_fiscais").fetchone()) == (5, 3106, "danfse", 100)
    assert conn.execute("SELECT nota_id FROM baixas").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='notas_fiscais_nova'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='idx_nf_coligada_idmov'").fetchone()[0] == 1
