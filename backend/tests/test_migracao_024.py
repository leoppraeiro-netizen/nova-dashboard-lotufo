"""Migracao 024: seis tipos com chave, natureza da certidao, regularidade mensal, consorciadas."""
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


def test_seis_tipos_com_chave_e_link(conn):
    linhas = conn.execute("SELECT chave, link_emissao, aplicavel_por_padrao FROM certidao_tipos "
                          "WHERE chave IS NOT NULL ORDER BY id").fetchall()
    assert [r[0] for r in linhas] == ["federal", "fgts", "trabalhista", "estadual", "municipal", "falencia"]
    assert all(r[1].startswith("https://") for r in linhas)
    assert [r[2] for r in linhas] == [1, 1, 1, 1, 1, 0]      # a 031 passou estadual e municipal a padrao


def test_natureza_e_regularidade_com_check(conn):
    conn.execute("INSERT INTO certidoes (entidade_id, tipo_id, emissao, validade, arquivo, sha256, origem, natureza, leitura) "
                 "VALUES (1, 1, '2026-06-24', '2026-12-21', 'certidoes/x.pdf', ?, 'upload', 'positiva_efeito_negativa', 'automatica')",
                 ("a" * 64,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO certidoes (entidade_id, tipo_id, emissao, validade, arquivo, sha256, origem, natureza) "
                     "VALUES (1, 1, '2026-06-24', '2026-12-21', 'certidoes/x.pdf', ?, 'upload', 'positiva')", ("a" * 64,))
    conn.execute("INSERT INTO regularidades (entidade_id, competencia, arquivo, sha256, tamanho) "
                 "VALUES (1, '2026-07', 'regularidades/x.pdf', ?, 10)", ("b" * 64,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO regularidades (entidade_id, competencia, arquivo, sha256, tamanho) "
                     "VALUES (1, '07/2026', 'regularidades/x.pdf', ?, 10)", ("b" * 64,))


def test_reexecucao_nao_duplica_tipos(conn):
    sql = (db.MIGRATIONS_DIR / "024_documentos.sql").read_text(encoding="utf-8")
    conn.executescript(db._sem_alters_ja_aplicados(conn, sql))
    assert conn.execute("SELECT COUNT(*) FROM certidao_tipos WHERE chave IS NOT NULL").fetchone()[0] == 6


def test_competencia_com_mes_invalido_e_recusada(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO regularidades (entidade_id, competencia, arquivo, sha256, tamanho) "
                     "VALUES (1, '2026-13', 'regularidades/x.pdf', ?, 10)", ("b" * 64,))
