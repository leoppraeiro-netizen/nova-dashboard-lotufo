"""Migracao 021 (bloco 3): notas_fiscais com origem pdf (idmov NULL), confirmacao pelo RM, nota_emitida_em, cnpj do orgao."""
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


def _colunas(conn, tabela):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")}


def test_colunas_novas(conn):
    nf = _colunas(conn, "notas_fiscais")
    for col in ("numero_int", "origem", "documento_id", "prestador_cnpj", "tomador_cnpj", "competencia",
                "municipio", "natureza_lida", "numero_medicao_lido", "valor_pdf_centavos", "iss_centavos",
                "inss_centavos", "irrf_centavos", "ibs_centavos", "cbs_centavos", "liquido_centavos",
                "confirmacao", "confirmada_em", "conferencia", "justificativa", "leitura"):
        assert col in nf, col
    assert "nota_emitida_em" in _colunas(conn, "medicoes")
    assert "cnpj" in _colunas(conn, "orgaos")


def test_nota_do_pdf_sem_idmov_e_unicidade_parcial(conn):
    conn.execute("INSERT INTO notas_fiscais (coligada, numero, numero_int, valor_centavos, origem, confirmacao) "
                 "VALUES (1, '3103', 3103, 100, 'pdf', 'aguardando_rm')")
    conn.execute("INSERT INTO notas_fiscais (coligada, numero, numero_int, valor_centavos, origem, confirmacao) "
                 "VALUES (1, '2261', 2261, 100, 'pdf', 'aguardando_rm')")   # dois NULL em idmov convivem
    conn.execute("INSERT INTO notas_fiscais (coligada, idmov, numero, numero_int, valor_centavos) "
                 "VALUES (1, 77, '000002262', 2262, 100)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO notas_fiscais (coligada, idmov, numero, numero_int, valor_centavos) "
                     "VALUES (1, 77, '000002263', 2263, 100)")
    assert tuple(conn.execute("SELECT origem, confirmacao FROM notas_fiscais WHERE idmov=77").fetchone()) == ("rm", "so_rm")
    # nota sem idmov so' pode ser do PDF
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO notas_fiscais (coligada, numero, numero_int, valor_centavos) VALUES (1, '9', 9, 1)")


def test_filhas_de_notas_sobrevivem_a_reexecucao(conn):
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos) "
                 "VALUES ('SINFRA','X/2026','obra',100)")
    conn.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia, estado) "
                 "VALUES (1, 1, 'execucao', '2026-05', 'protocolada')")
    conn.execute("INSERT INTO notas_fiscais (coligada, idmov, numero, numero_int, valor_centavos) "
                 "VALUES (1, 5, '000000005', 5, 100)")
    conn.execute("INSERT INTO baixas (coligada, idlan, nota_id, valor_original_centavos, status_lan) VALUES (1, 9, 1, 100, 1)")
    conn.execute("INSERT INTO nf_alocacoes (medicao_id, nota_id, valor_alocado_centavos, origem) VALUES (1, 1, 100, 'manual')")
    conn.commit()
    # reexecucao como o runner faz: os ALTER ja' aplicados sao aparados (test_migracao_020 faz igual)
    sql = (db.MIGRATIONS_DIR / "021_notas.sql").read_text(encoding="utf-8")
    conn.executescript(db._sem_alters_ja_aplicados(conn, sql))
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("SELECT COUNT(*) FROM notas_fiscais").fetchone()[0] == 1
    assert conn.execute("SELECT nota_id FROM baixas").fetchone()[0] == 1
    assert conn.execute("SELECT numero_int FROM notas_fiscais").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='notas_fiscais_nova'").fetchone()[0] == 0
