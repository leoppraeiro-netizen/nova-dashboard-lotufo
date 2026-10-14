"""Matriz de certidões sem N+1 (dívida da fase 3, issue #66).

O painel lê o histórico numa vez só e agrupa por par em Python; tem que dar o mesmo que as perguntas
por par (`vigente`, `nao_se_aplica_vigora`, `ultima_emissao`) e não crescer em consultas com o
número de entidades.
"""
import datetime

import pytest
from app import auth, certidoes, db, entidades, tempo

CNPJS = ["31200707000175", "31200808000146", "31200909000117", "31201010000119"]


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@l.com", "senha-forte-123", "admin")
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    yield c
    c.close()


def _reg(conn, ent, tipo, emissao, validade):
    return certidoes.registrar(conn, 1, ent, tipo, emissao, validade,
                               f"dados/certidoes/{ent}-{tipo}-{emissao}.pdf", "a" * 64, "robo")


def _entidade(conn, n):
    return entidades.criar(conn, 1, {"nome": f"Construtora {n}", "papel": "lotufo", "cnpj": CNPJS[n]})


def _por_par(conn, hoje):
    """Referência: as três perguntas por par, uma a uma (a forma antiga do painel)."""
    ref = {}
    for e in entidades.listar(conn):
        for t in certidoes.tipos(conn):
            v = certidoes.vigente(conn, e["id"], t["id"], na_data=hoje)
            nsa = certidoes.nao_se_aplica_vigora(conn, e["id"], t["id"])
            ult = None if v else certidoes.ultima_emissao(conn, e["id"], t["id"], hoje)
            ref[(e["id"], t["id"])] = (v, nsa, ult)
    return ref


def test_painel_bate_com_as_perguntas_por_par(conn, monkeypatch):
    e2 = _entidade(conn, 0)
    _reg(conn, 1, 1, "2026-08-01", "2026-11-01")                 # vigente
    _reg(conn, 1, 3, "2026-05-01", "2026-08-01")                 # vencida
    _reg(conn, 1, 3, "2026-04-01", "2026-07-01")                 # vencida mais antiga, id maior
    rev = _reg(conn, 1, 4, "2026-08-01", "2026-11-01")
    certidoes.marcar_estado(conn, 1, rev, "revogada", "erro")    # revogada hoje
    _reg(conn, 1, 5, "2026-09-15", "2026-12-01")                 # emissao FUTURA: nao vale hoje
    _reg(conn, 1, 6, "2026-08-20", "2026-12-31")                 # duas cobrem hoje: manda a de
    _reg(conn, 1, 6, "2026-08-01", "2026-10-01")                 # maior validade, mesmo gravada antes
    _reg(conn, 1, 2, "2026-08-01", "2026-11-01")
    adiante = lambda: datetime.date(2026, 9, 10)                 # noqa: E731
    hoje = tempo.hoje_local
    monkeypatch.setattr(tempo, "hoje_local", adiante)
    certidoes.marcar_estado(conn, 1, conn.execute(
        "SELECT MAX(id) i FROM certidoes").fetchone()["i"], "revogada", "erro")
    monkeypatch.setattr(tempo, "hoje_local", hoje)               # revogada em 10/09: hoje ainda vale
    _reg(conn, e2, 1, "2026-01-01", "2026-02-01")                # vencida em outra entidade
    certidoes.marcar_nao_se_aplica(conn, 1, e2, 2, "sem empregados")
    ref = _por_par(conn, "2026-09-01")
    linhas = certidoes.painel(conn)
    assert len(linhas) == len(ref)
    for l in linhas:
        v, nsa, ult = ref[(l["entidade_id"], l["tipo_id"])]
        assert l["vigente"] == v and l["ultima"] == ult, l
        assert (l["motivo"] == "nao_se_aplica") == (nsa and v is None), l
    assert [(l["entidade_id"], l["tipo_id"]) for l in linhas] == [
        (e["id"], t["id"]) for e in entidades.listar(conn) for t in certidoes.tipos(conn)]


def test_painel_nao_faz_consulta_por_entidade(conn):
    def contar():
        vistos = []
        conn.set_trace_callback(vistos.append)
        certidoes.painel(conn)
        conn.set_trace_callback(None)
        return len(vistos)

    antes = contar()
    for i in range(3):
        e = _entidade(conn, i)
        _reg(conn, e, 1, "2026-08-01", "2026-11-01")
    assert contar() == antes
