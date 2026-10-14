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


def test_cria_tabelas_e_colunas(conn):
    assert {"chave", "familia", "regras"} <= _colunas(conn, "orgaos")
    assert {"nome_curto", "orgao_id", "lei", "cno", "encerramento_iniciado_em",
            "sem_reajuste", "destinatarios_extras"} <= _colunas(conn, "contratos")
    assert {"chave_cadastro", "forma"} <= _colunas(conn, "aditivos")
    assert {"chave", "sigla_oficio"} <= _colunas(conn, "entidades")
    assert {"contrato_id", "chave", "tipo", "dados"} <= _colunas(conn, "instrumentos")


def test_reaplicar_e_inofensivo_e_adota_o_aditivo_da_carga_legada(conn):
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos) "
                 "VALUES ('SINFRA','1/2024','obra',100)")
    conn.execute("INSERT INTO aditivos (contrato_id, tipo, delta_valor_centavos, status, data_assinatura, "
                 "objeto) VALUES (1,'valor',50,'assinado','2026-08-04','Carga inicial: soma dos aditivos')")
    conn.commit()
    sql = (db.MIGRATIONS_DIR / "018_cadastro_versionado.sql").read_text(encoding="utf-8")
    conn.executescript(db._sem_alters_ja_aplicados(conn, sql))
    linha = conn.execute("SELECT chave_cadastro, forma FROM aditivos").fetchone()
    assert (linha["chave_cadastro"], linha["forma"]) == ("carga-legado", "termo_aditivo")


def test_nome_curto_e_unico(conn):
    base = "INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos, nome_curto) "
    conn.execute(base + "VALUES ('A','1','o',1,'MT-402')")
    with pytest.raises(Exception):
        conn.execute(base + "VALUES ('A','2','o',1,'MT-402')")
