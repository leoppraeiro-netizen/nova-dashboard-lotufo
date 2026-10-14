"""O conftest (issue #88) entrega aos testes uma COPIA de um banco migrado uma vez por sessao, no
lugar de rodar as migracoes num banco vazio a cada teste. Este modulo NAO leva a marca
`migracao_real`, de proposito: aqui `db.migrate` e' a versao trocada pelo conftest, a mesma que
os outros ~900 testes recebem, e e' ela que se compara com o runner de verdade."""
from app import db
from tests.conftest import _migrate_real


def _retrato(conn):
    schema = set(conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master").fetchall())
    tabelas = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    linhas = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tabelas}
    aplicadas = {r[0] for r in conn.execute("SELECT nome FROM schema_migrations")}
    return schema, linhas, aplicadas


def test_copia_do_conftest_e_igual_ao_migrate_real(tmp_path, monkeypatch):
    """Mesmo schema, mesmas linhas semeadas (tipos de certidao da 006, tipos de documento da
    024...) e mesma lista em schema_migrations. Se a regra de "banco vazio" ou o jeito de copiar
    mudar em `migrate_pela_copia`, e' aqui que acusa -- nos outros testes passaria calado."""
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "real.db"))
    real = db.get_conn()
    _migrate_real(real)

    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "copia.db"))
    copia = db.get_conn()
    db.migrate(copia)  # a versao do conftest: copia do banco-modelo

    schema_real, linhas_real, aplicadas_real = _retrato(real)
    schema_copia, linhas_copia, aplicadas_copia = _retrato(copia)
    assert schema_copia == schema_real
    assert linhas_copia == linhas_real
    assert aplicadas_copia == aplicadas_real == {p.name for p in db.MIGRATIONS_DIR.glob("*.sql")}
    assert copia.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert any(linhas_copia.values()), "as migracoes semeiam linhas; a copia nao pode vir vazia"
    real.close(); copia.close()


def test_segundo_migrate_na_copia_e_o_runner_real_e_nao_duplica(tmp_path, monkeypatch):
    """Banco que ja tem tabela segue pelo runner de verdade (e' o caminho de quem apaga uma linha
    de schema_migrations para reaplicar uma migracao): nada e' aplicado de novo."""
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()
    db.migrate(conn)
    antes = _retrato(conn)
    db.migrate(conn)
    assert _retrato(conn) == antes
    conn.close()
