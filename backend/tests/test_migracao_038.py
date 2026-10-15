"""Migracao 038 (issue #61): o historico de atesto que ja' existe na auditoria vira evento, sem duplicar."""
import pytest

from app import auth, contratos, db, medicoes

# Exercita a propria migracao: parte de um banco vazio de verdade, sem o banco-modelo do conftest.
pytestmark = pytest.mark.migracao_real


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    c.execute("UPDATE certidao_tipos SET aplicavel_por_padrao=0"); c.commit()
    auth.criar_usuario(c, "U", "u@l.com", "senha-forte-123", "engenharia")
    yield c
    c.close()


def _como_antes_da_038(c):
    """Banco "ate' a 037": sem a tabela de eventos (so' em teste; a migracao nunca apaga nada)."""
    c.execute("DROP TABLE medicao_atestos")
    c.execute("DELETE FROM schema_migrations WHERE nome='038_medicao_atestos.sql'"); c.commit()


def _eventos(c):
    return [tuple(r) for r in c.execute(
        "SELECT medicao_id, valor_centavos, origem, atestado_em, usuario_id FROM medicao_atestos ORDER BY id")]


def test_038_carrega_o_historico_da_auditoria_e_reexecutar_nao_duplica(conn):
    cid = contratos.criar(conn, 1, {"orgao": "SINFRA", "numero_instrumento": "IC 1/2026", "objeto": "Obra X",
                                    "valor_original_centavos": 100_000_00})
    a = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    b = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 2, "tipo": "execucao", "competencia": "2026-08"})
    medicoes.definir_valor(conn, 1, a, "atestado", 1_000_01, "manual", "2026-08-20")
    medicoes.definir_valor(conn, None, a, "atestado", 999_99, "detectado")
    _como_antes_da_038(conn)
    # vigente gravado sem auditoria (nao deveria existir, mas a rede de seguranca cobre): entra "pelo sistema"
    conn.execute("UPDATE medicoes SET valor_atestado_centavos=5_00, valor_atestado_origem='aceito' WHERE id=?", (b,))
    conn.commit()
    db.migrate(conn)
    esperado = [(a, 1_000_01, "manual", "2026-08-20", 1), (a, 999_99, "detectado", "2026-08-20", None),
                (b, 5_00, "aceito", None, None)]
    assert _eventos(conn) == esperado
    assert [e["texto"] for e in medicoes.edicoes_valor(conn, [a])[a]] == [
        "Atestado definido em R$ 1.000,01 por U",
        "Atestado alterado de R$ 1.000,01 para R$ 999,99 pelo sistema"]
    conn.execute("DELETE FROM schema_migrations WHERE nome='038_medicao_atestos.sql'"); conn.commit()
    db.migrate(conn)
    assert _eventos(conn) == esperado
