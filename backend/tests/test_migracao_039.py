"""Migracao 039 (issue #61): o historico de atesto que ja' existe na auditoria vira evento, sem duplicar."""
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


def _como_antes_da_039(c):
    """Banco "ate' a 038": sem a tabela de eventos (so' em teste; a migracao nunca apaga nada)."""
    c.execute("DROP TABLE medicao_atestos")
    c.execute("DELETE FROM schema_migrations WHERE nome='039_medicao_atestos.sql'"); c.commit()


def _eventos(c):
    return [tuple(r) for r in c.execute(
        "SELECT medicao_id, valor_centavos, origem, atestado_em, usuario_id FROM medicao_atestos ORDER BY id")]


def test_039_carrega_o_historico_da_auditoria_e_reexecutar_nao_duplica(conn):
    cid = contratos.criar(conn, 1, {"orgao": "SINFRA", "numero_instrumento": "IC 1/2026", "objeto": "Obra X",
                                    "valor_original_centavos": 100_000_00})
    a = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    b = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 2, "tipo": "execucao", "competencia": "2026-08"})
    medicoes.definir_valor(conn, 1, a, "atestado", 1_000_01, "manual", "2026-08-20")
    medicoes.definir_valor(conn, None, a, "atestado", 999_99, "detectado")
    _como_antes_da_039(conn)
    # auditoria antiga, de antes de o dia ir no `depois`: o dia que valia (`antes`) segue valendo
    from app import auditoria
    with db.mutacao(conn):
        auditoria.registrar(conn, 1, "medicao.valor_atestado", "medicao", a,
                            {"valor_atestado_centavos": 999_99, "atestado_em": "2026-08-20"},
                            {"valor_atestado_centavos": 999_98, "valor_atestado_origem": "manual"})
    conn.execute("UPDATE medicoes SET valor_atestado_centavos=999_98 WHERE id=?", (a,))
    # vigente gravado sem auditoria (nao deveria existir, mas a rede de seguranca cobre): entra "pelo sistema",
    # com a hora da migracao
    conn.execute("UPDATE medicoes SET valor_atestado_centavos=5_00, valor_atestado_origem='aceito', "
                 "atestado_em='2026-09-01' WHERE id=?", (b,))
    conn.commit()
    db.migrate(conn)
    esperado = [(a, 1_000_01, "manual", "2026-08-20", 1), (a, 999_99, "detectado", "2026-08-20", None),
                (a, 999_98, "manual", "2026-08-20", 1), (b, 5_00, "aceito", "2026-09-01", None)]
    assert _eventos(conn) == esperado
    # gate Sol S2: o evento de reconciliacao tem a hora da migracao (UTC), nao o dia do atesto a meia-noite
    assert conn.execute("SELECT criado_em FROM medicao_atestos WHERE medicao_id=?", (b,)).fetchone()[0] != \
        "2026-09-01 00:00:00"
    assert [e["texto"] for e in medicoes.edicoes_valor(conn, [a])[a]] == [
        "Atestado definido em R$ 1.000,01 por U",
        "Atestado alterado de R$ 1.000,01 para R$ 999,99 pelo sistema",
        "Atestado alterado de R$ 999,99 para R$ 999,98 por U"]
    conn.execute("DELETE FROM schema_migrations WHERE nome='039_medicao_atestos.sql'"); conn.commit()
    db.migrate(conn)
    assert _eventos(conn) == esperado


def test_039_reconciliacao_entra_depois_dos_eventos_na_linha_do_tempo(conn):
    """Revisor R2: com a hora no dia do atesto a meia-noite, o evento de reconciliacao ia para o comeco da lista,
    e o "de X para Y" (montado pela ordem dos eventos) saia fora de ordem."""
    cid = contratos.criar(conn, 1, {"orgao": "SINFRA", "numero_instrumento": "IC 1/2026", "objeto": "Obra X",
                                    "valor_original_centavos": 100_000_00})
    c = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    medicoes.definir_valor(conn, 1, c, "atestado", 100_01, "manual", "2026-08-20")
    medicoes.definir_valor(conn, 1, c, "atestado", 90_01, "manual")
    _como_antes_da_039(conn)
    conn.execute("UPDATE medicoes SET valor_atestado_centavos=80_01 WHERE id=?", (c,)); conn.commit()
    db.migrate(conn)
    assert [e["texto"] for e in medicoes.edicoes_valor(conn, [c])[c]] == [
        "Atestado definido em R$ 100,01 por U",
        "Atestado alterado de R$ 100,01 para R$ 90,01 por U",
        "Atestado alterado de R$ 90,01 para R$ 80,01 pelo sistema"]
