"""A divida estrutural da fase 2: mutacao e auditoria no MESMO commit.

O teste central e o inverso do experimento da T4/fase 2: uma falha no meio de
uma mutacao composta nao pode deixar medicao orfa nem auditoria do que nao ficou.
"""
import sqlite3

import pytest
from unittest.mock import patch
from app import auth, contratos, db, medicoes, auditoria

@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@l.com", "senha-forte-123", "engenharia")
    yield c
    c.close()

@pytest.fixture
def cid(conn):
    return contratos.criar(conn, 1, {"orgao": "S", "numero_instrumento": "IC 1",
                                     "objeto": "X", "valor_original_centavos": 100_00})

def test_registrar_sem_transacao_falha_alto(conn):
    with pytest.raises(RuntimeError, match="transação aberta"):
        auditoria.registrar(conn, 1, "x.y", "x", 1, None, {})

def test_mutacao_commita_junto(conn, cid):
    medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 1,
                             "tipo": "execucao", "competencia": "2026-07"})
    outra = db.get_conn()
    try:
        assert outra.execute("SELECT COUNT(*) c FROM medicoes").fetchone()["c"] == 1
        assert outra.execute("SELECT COUNT(*) c FROM audit_log WHERE acao='medicao.criar'").fetchone()["c"] == 1
    finally:
        outra.close()
    assert not conn.in_transaction  # nada pendurado

def test_falha_no_meio_desfaz_tudo(conn, cid):
    # mutacao composta (criar + definir_valor) com falha APOS criar a medicao: nada pode sobrar.
    # Era sugestoes.decidir ate' o bloco 9; o envelope reentrante e' o mesmo.
    def compor():
        with db.mutacao(conn):
            mid = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 9, "tipo": "execucao",
                                           "competencia": "2026-07"})
            medicoes.definir_valor(conn, 1, mid, "valor_protocolado_centavos", 5_00, "manual")
    with patch.object(medicoes, "definir_valor", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            compor()
    conn.rollback()  # simula o fim da requisicao
    assert medicoes.listar(conn, cid) == []                       # sem medicao orfa
    from app.auditoria import verificar_cadeia
    assert verificar_cadeia(conn)                                  # cadeia integra
    # ... e a cadeia nao pode ter guardado NADA da tentativa revertida: a auditoria
    # que descreve um dado inexistente e tao ruim quanto o dado sem auditoria.
    assert [r["acao"] for r in conn.execute("SELECT acao FROM audit_log ORDER BY id")] == ["contrato.criar"]

def test_cadeia_serializada_sob_transacao(conn, cid):
    # duas mutacoes em sequencia mantem a cadeia encadeada corretamente
    medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 2, "tipo": "execucao", "competencia": "2026-08"})
    from app.auditoria import verificar_cadeia
    assert verificar_cadeia(conn)


# --- fix round 1 -------------------------------------------------------------

def test_begin_immediate_serializa_escritores_de_verdade(conn, cid):
    """O envelope nao apenas "agrupa": ele SERIALIZA escritores.

    Enquanto A segura a mutacao, B nao consegue nem abrir a dele -- o BEGIN IMMEDIATE
    de B espera o lock de escrita e estoura o busy_timeout. Assim que A commita, B
    passa. E' esta propriedade que garante que a leitura do head da cadeia de auditoria
    acontece sob lock (sem fork).
    """
    outra = db.get_conn()
    outra.execute("PRAGMA busy_timeout=100")  # nao esperar os 5s do padrao no teste
    try:
        with db.mutacao(conn):
            conn.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia) "
                         "VALUES (?,1,'execucao','2026-07')", (cid,))
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                with db.mutacao(outra):
                    pass  # nem chega aqui: o BEGIN IMMEDIATE de B ja falha
        # A commitou e soltou o lock: agora B escreve normalmente
        with db.mutacao(outra):
            outra.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia) "
                          "VALUES (?,2,'execucao','2026-08')", (cid,))
        assert [m["numero"] for m in medicoes.listar(conn, cid)] == [1, 2]
        # o envelope que falhou no BEGIN nao deixou marcador pendurado
        assert not db.em_mutacao(outra)
    finally:
        outra.close()


def test_transacao_crua_nao_e_envelope(conn, cid):
    """`in_transaction` sozinho nao autoriza nada.

    Um DML cru abre transacao implicita que NAO tem dono. Se `mutacao` a adotasse,
    commitaria escrita de terceiro no meio do caminho; se `registrar` a aceitasse, a
    cadeia seria escrita sem a serializacao que a protege de forkar.
    """
    conn.execute("UPDATE contratos SET objeto='cru' WHERE id=?", (cid,))  # sem commit
    assert conn.in_transaction and not db.em_mutacao(conn)
    with pytest.raises(RuntimeError, match="fora de db.mutacao"):
        with db.mutacao(conn):
            pass
    with pytest.raises(RuntimeError, match="transação aberta"):
        auditoria.registrar(conn, 1, "x.y", "x", 1, None, {})
    conn.rollback()


def test_reentrante_desfaz_so_a_parte_interna(conn, cid):
    """SAVEPOINT no ramo reentrante: o bloco interno que falha nao contamina o commit.

    Sem ponto de retorno proprio, se o chamador externo capturasse a excecao do bloco
    interno e seguisse, o commit externo levaria junto o que o interno chegou a
    escrever antes de morrer.
    """
    with db.mutacao(conn):
        medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 1,
                                 "tipo": "execucao", "competencia": "2026-07"})
        with pytest.raises(ValueError, match="já existe"):
            with db.mutacao(conn):     # bloco interno: escreve e morre
                conn.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia) "
                             "VALUES (?,7,'execucao','2026-09')", (cid,))
                medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 1,
                                         "tipo": "execucao", "competencia": "2026-08"})
        # o externo segue vivo e commita SO' o que era dele
    assert [m["numero"] for m in medicoes.listar(conn, cid)] == [1]   # a 7 foi desfeita
    from app.auditoria import verificar_cadeia
    assert verificar_cadeia(conn)
    assert not conn.in_transaction


def test_exigir_uma_linha_e_o_unico_lugar_da_corrida_perdida(conn, cid):
    """Dívida da fase 3: o "rowcount != 1 -> ValueError" dos UPDATEs condicionais mora em db.py."""
    with db.mutacao(conn):
        ganhou = conn.execute("UPDATE contratos SET estado='ativo' WHERE id=? AND estado='ativo'", (cid,))
        db.exigir_uma_linha(ganhou, "nunca")
        perdeu = conn.execute("UPDATE contratos SET estado='ativo' WHERE id=? AND estado='encerrado'", (cid,))
        with pytest.raises(ValueError, match="mudou concorrentemente"):
            db.exigir_uma_linha(perdeu, "Estado mudou concorrentemente; tente novamente")
