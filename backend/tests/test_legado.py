"""Remapeamento do legado (bloco 3): nf_emitida -> protocolada, prevista sem valor -> cancelada, recebida fica."""
import pytest

from app import auditoria, auth, cli, contratos, db, legado, medicoes

# Exercita a propria migracao: parte de um banco vazio de verdade, sem o banco-modelo do
# conftest (issue #88).
pytestmark = pytest.mark.migracao_real


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    c.execute("UPDATE certidao_tipos SET aplicavel_por_padrao=0"); c.commit()
    auth.criar_usuario(c, "U", "u@l.com", "senha-forte-123", "admin")
    yield c
    c.close()


def _semear(conn):
    cid = contratos.criar(conn, 1, {"orgao": "SINFRA", "numero_instrumento": "IC 1/2025", "objeto": "Obra",
                                    "valor_original_centavos": 10_000_000_00})
    a = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 1, "tipo": "execucao", "competencia": "2026-03"})
    medicoes.definir_valor(conn, 1, a, "protocolado", 1000, "manual")
    medicoes.registrar_protocolo(conn, 1, a, "2026-03-31", None, None, "manual")
    conn.execute("UPDATE medicoes SET estado='nf_emitida', nf_emitida_em='2026-04-02' WHERE id=?", (a,)); conn.commit()
    b = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 2, "tipo": "execucao", "competencia": "2026-04"})
    medicoes.definir_valor(conn, 1, b, "protocolado", 1000, "manual")
    medicoes.registrar_protocolo(conn, 1, b, "2026-04-30", None, None, "manual")
    conn.execute("UPDATE medicoes SET estado='recebida', recebida_em='2026-06-01' WHERE id=?", (b,)); conn.commit()
    c = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 3, "tipo": "execucao", "competencia": "2026-05"})   # prevista sem valor
    d = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 4, "tipo": "execucao", "competencia": "2026-06"})
    medicoes.definir_valor(conn, 1, d, "protocolado", 5, "manual")                                                  # prevista com valor
    # nf_emitida SEM data de marco mas com NF do RM alocada: a data vem da emissao da nota
    e = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 5, "tipo": "execucao", "competencia": "2026-05"})
    medicoes.definir_valor(conn, 1, e, "protocolado", 700, "manual")
    medicoes.registrar_protocolo(conn, 1, e, "2026-05-31", None, None, "manual")
    conn.execute("UPDATE medicoes SET estado='nf_emitida' WHERE id=?", (e,)); conn.commit()
    conn.execute("INSERT INTO notas_fiscais (coligada, idmov, numero, numero_int, emissao, valor_centavos) "
                 "VALUES (1, 5, '000000005', 5, '2026-06-03', 700)")
    conn.execute("INSERT INTO nf_alocacoes (medicao_id, nota_id, valor_alocado_centavos, origem, regra) "
                 "VALUES (?, 1, 700, 'manual', 'ledger_rm')", (e,))
    conn.commit()
    return a, b, c, d, e


def test_ensaio_relata_e_nao_grava(conn):
    a, b, c, d, e = _semear(conn)
    rel = legado.remapear(conn, 1, ensaio=True)
    assert rel == {"nf_emitida_para_protocolada": 2, "prevista_sem_valor_cancelada": 1, "recebida_mantida": 1, "ensaio": True}
    assert medicoes.detalhe(conn, a)["estado"] == "nf_emitida"
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE json_extract(depois, '$.motivo')=?", (legado.MOTIVO,)).fetchone()[0] == 0
    # a conexao continua usavel depois do rollback do ensaio
    conn.execute("SELECT 1").fetchone()


def test_remapeia_audita_e_e_idempotente(conn):
    a, b, c, d, e = _semear(conn)
    rel = legado.remapear(conn, 1, ensaio=False)
    assert (rel["nf_emitida_para_protocolada"], rel["prevista_sem_valor_cancelada"], rel["ensaio"]) == (2, 1, False)
    ma, mc, md, me = (medicoes.detalhe(conn, x) for x in (a, c, d, e))
    assert (ma["estado"], ma["nota_emitida_em"]) == ("protocolada", "2026-04-02")
    assert (me["estado"], me["nota_emitida_em"]) == ("protocolada", "2026-06-03")     # data da NF alocada
    assert (mc["estado"], mc["motivo_represamento"]) == ("cancelada", legado.MOTIVO_PREVISTA)
    assert md["estado"] == "prevista"
    assert medicoes.detalhe(conn, b)["estado"] == "recebida"
    assert conn.execute("SELECT COUNT(*) FROM medicoes WHERE estado='nf_emitida'").fetchone()[0] == 0
    assert auditoria.verificar_cadeia(conn)
    de_novo = legado.remapear(conn, 1, ensaio=False)
    assert (de_novo["nf_emitida_para_protocolada"], de_novo["prevista_sem_valor_cancelada"]) == (0, 0)


def test_cli_legado_remapear(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    c.execute("UPDATE certidao_tipos SET aplicavel_por_padrao=0"); c.commit()
    auth.criar_usuario(c, "U", "u@l.com", "senha-forte-123", "admin")
    _semear(c); c.close()
    assert cli.main(["legado", "remapear", "--usuario", "u@l.com", "--ensaio"]) == 0
    saida = capsys.readouterr().out
    assert "ENSAIO" in saida and "nf_emitida_para_protocolada: 2" in saida
    assert cli.main(["legado", "remapear", "--usuario", "ninguem@l.com"]) == 1
    assert cli.main(["legado", "remapear", "--usuario", "u@l.com"]) == 0
    assert "APLICADO" in capsys.readouterr().out
    c = db.get_conn()
    assert c.execute("SELECT COUNT(*) FROM medicoes WHERE estado='nf_emitida'").fetchone()[0] == 0
    c.close()
