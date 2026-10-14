"""Migracao 026: pleitos, medicao final e folga por contrato (bloco 7)."""
from app import db
import pytest

# Exercita a propria migracao: parte de um banco vazio de verdade, sem o banco-modelo do
# conftest (issue #88).
pytestmark = pytest.mark.migracao_real


def _colunas(c, tabela):
    return {r[1] for r in c.execute(f"PRAGMA table_info({tabela})")}


def test_026_cria_tabelas_e_colunas_e_e_idempotente(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn()
    db.migrate(c)
    db.migrate(c)                       # reexecucao nao falha nem duplica
    assert {"tipo", "origem", "data_base_mes", "ciclo", "dias", "justificativa", "numero_oficio", "corpo_carta",
            "montado_arquivo", "assinado_arquivo", "conferencia", "envio_id", "enviado_em", "situacao"} \
        <= _colunas(c, "pleitos")
    assert {"pleito_id", "tipo", "nome", "arquivo", "sha256", "tamanho", "ext", "removido_em"} \
        <= _colunas(c, "pleito_anexos")
    assert {"final", "final_em"} <= _colunas(c, "medicoes") and "folga_vigencia_dias" in _colunas(c, "contratos")
    c.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos) VALUES ('X','1','o',1)")
    c.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia) VALUES (1, 1, 'execucao', '2026-01')")
    assert c.execute("SELECT final FROM medicoes").fetchone()[0] == 0
    c.close()
