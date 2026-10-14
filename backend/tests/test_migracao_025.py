"""Migracao 025: protocolo feito pelo sistema (bloco 5)."""
from app import db
import pytest

# Exercita a propria migracao: parte de um banco vazio de verdade, sem o banco-modelo do
# conftest (issue #88).
pytestmark = pytest.mark.migracao_real


def _colunas(c, tabela):
    return {r[1] for r in c.execute(f"PRAGMA table_info({tabela})")}


def test_025_cria_tabelas_e_colunas_e_e_idempotente(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn()
    db.migrate(c)
    db.migrate(c)                       # reexecucao nao falha nem duplica
    assert {"etapa", "natureza", "numero_oficio", "corpo_carta", "montado_arquivo", "assinado_arquivo",
            "conferencia", "envio_id", "justificativa", "numero_orgao", "situacao"} <= _colunas(c, "protocolos")
    assert {"protocolo_id", "medicao_id"} <= _colunas(c, "protocolo_medicoes")
    assert {"tipo", "nome", "arquivo", "sha256", "tamanho", "ext", "removida_em"} <= _colunas(c, "protocolo_pecas")
    assert "protocolo_id" in _colunas(c, "medicao_protocolos")
    assert {"objeto_completo", "cno_arquivo"} <= _colunas(c, "contratos")
    assert {"cargo", "tratamento", "portaria"} <= _colunas(c, "contrato_fiscais")
    c.close()
