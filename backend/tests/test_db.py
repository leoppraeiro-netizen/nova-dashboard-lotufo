import pytest
from app import db

# Estes testes exercitam o proprio runner de migracao: partem de um banco vazio de verdade,
# sem o banco-modelo do conftest (issue #88).
pytestmark = pytest.mark.migracao_real

def test_conn_endurecida(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    conn.close()

def test_db_path_exige_variavel_fora_de_dev(tmp_path, monkeypatch):
    import pytest
    monkeypatch.delenv("DASH_DB_PATH", raising=False)
    monkeypatch.delenv("DASH_DEV", raising=False)
    with pytest.raises(RuntimeError, match="DASH_DB_PATH"):
        db.db_path()
    monkeypatch.setenv("DASH_DEV", "1")
    monkeypatch.chdir(tmp_path)
    assert db.db_path().name == "dashboard.db"

def test_migrate_aplica_uma_vez(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()
    db.migrate(conn)
    db.migrate(conn)  # idempotente
    tabelas = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"usuarios", "sessoes", "audit_log", "schema_migrations"} <= tabelas
    conn.close()

def test_migrate_recupera_de_estado_parcial(tmp_path, monkeypatch):
    """executescript nao e transacional: uma migracao pode ter criado as tabelas
    sem chegar a registrar o nome em schema_migrations. A reaplicacao precisa
    passar sem erro (migracoes idempotentes)."""
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()

    # simula estado parcial: script aplicado, registro nao gravado
    sql_file = db.MIGRATIONS_DIR / "001_usuarios_sessoes_audit.sql"
    conn.executescript(sql_file.read_text(encoding="utf-8"))
    conn.commit()

    db.migrate(conn)  # nao pode levantar

    aplicadas = {r[0] for r in conn.execute("SELECT nome FROM schema_migrations")}
    assert sql_file.name in aplicadas
    tabelas = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"usuarios", "sessoes", "audit_log", "schema_migrations"} <= tabelas
    conn.close()

def test_migrate_reaplica_add_column_sem_erro(tmp_path, monkeypatch):
    """ADD COLUMN e' a unica DDL deste projeto sem forma idempotente no SQLite.

    Estado parcial de uma migracao que ALTERA tabela (008): a coluna ja existe e o
    nome nao chegou a `schema_migrations`. Sem a guarda do runner, a reaplicacao
    morre com "duplicate column name: estado_em" e o banco fica travado no lugar.
    """
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()
    db.migrate(conn)
    assert "estado_em" in {r[1] for r in conn.execute("PRAGMA table_info(certidoes)")}

    conn.execute("DELETE FROM schema_migrations WHERE nome=?",
                 ("008_certidoes_estado_em.sql",))
    conn.commit()
    db.migrate(conn)          # nao pode levantar

    colunas = [r[1] for r in conn.execute("PRAGMA table_info(certidoes)")]
    assert colunas.count("estado_em") == 1
    conn.close()

def test_alter_add_column_novo_nao_e_removido_do_script(tmp_path, monkeypatch):
    """A guarda so pula o que JA existe: uma coluna nova continua sendo criada."""
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()
    conn.execute("CREATE TABLE t (a INTEGER)")
    sql = "ALTER TABLE t ADD COLUMN a TEXT;\nALTER TABLE t ADD COLUMN b TEXT;\n"
    assert db._sem_alters_ja_aplicados(conn, sql).strip() == "ALTER TABLE t ADD COLUMN b TEXT;"
    conn.close()

def test_comentario_citando_alter_nao_engole_o_ddl_seguinte(tmp_path, monkeypatch):
    """Comentario `--` que MENCIONA um ALTER nao pode virar ALTER de verdade.

    A guarda casava dentro de comentario, e o `[^;]*;` dela atravessa linhas: um
    comentario historico ("ver ALTER TABLE t ADD COLUMN a") seguido de um CREATE
    virava UM casamento so, que ia do meio do comentario ate' o `;` do CREATE. Com a
    coluna citada ja existente, a guarda apagava o trecho inteiro -- e o CREATE
    sumia EM SILENCIO: migracao registrada como aplicada, tabela que nunca nasceu.
    """
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()
    conn.execute("CREATE TABLE t (a INTEGER)")
    sql = ("-- histórico: ver ALTER TABLE t ADD COLUMN a TEXT (já aplicado na 001)\n"
           "CREATE TABLE IF NOT EXISTS novo (id INTEGER PRIMARY KEY);\n")

    saida = db._sem_alters_ja_aplicados(conn, sql)

    assert "CREATE TABLE IF NOT EXISTS novo" in saida
    conn.executescript(saida)
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='novo'").fetchone()
    conn.close()

def test_comentario_no_fim_da_linha_do_alter_nao_confunde_a_guarda(tmp_path, monkeypatch):
    """ALTER real com comentario na mesma linha continua sendo pulado quando a coluna
    ja existe -- e o DDL seguinte continua intacto."""
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()
    conn.execute("CREATE TABLE t (a INTEGER)")
    sql = ("ALTER TABLE t ADD COLUMN a TEXT;  -- guardado pelo runner; ver db.migrate\n"
           "CREATE TABLE IF NOT EXISTS novo (id INTEGER PRIMARY KEY);\n")

    saida = db._sem_alters_ja_aplicados(conn, sql)

    assert "ADD COLUMN a TEXT" not in saida
    conn.executescript(saida)
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='novo'").fetchone()
    conn.close()

def test_migracao_009_e_idempotente_e_ancora_o_contrato_na_lotufo(tmp_path, monkeypatch):
    """`contratos.entidade_id` nasce apontando para a Lotufo (id 1).

    Sem DEFAULT na coluna, de proposito: o SQLite PROIBE `ADD COLUMN ... REFERENCES ...
    DEFAULT <valor>` (com foreign_keys=ON, um default nao-NULL numa coluna com FK nao
    e' aceito no ALTER). O ancoramento e' feito pelo UPDATE que acompanha o ALTER, e
    reaplicar a migracao (o cenario de `executescript` interrompido) tem que continuar
    passando: o ALTER e' pulado pela guarda do runner e o UPDATE e' inofensivo.
    """
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()
    db.migrate(conn)
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, "
                 "valor_original_centavos) VALUES ('S','IC 1','X',100)")
    conn.commit()
    assert conn.execute("SELECT entidade_id FROM contratos").fetchone()[0] is None

    conn.execute("DELETE FROM schema_migrations WHERE nome=?", ("009_contrato_entidade.sql",))
    conn.commit()
    db.migrate(conn)          # nao pode levantar
    db.migrate(conn)          # e' idempotente rodando de novo

    colunas = [r[1] for r in conn.execute("PRAGMA table_info(contratos)")]
    assert colunas.count("entidade_id") == 1
    # o UPDATE da reaplicacao ancorou o contrato legado na Lotufo
    assert conn.execute("SELECT entidade_id FROM contratos").fetchone()[0] == 1
    conn.close()

def test_migracao_010_remove_ia_chamadas_e_e_idempotente(tmp_path, monkeypatch):
    """A tabela de custo de IA (007) sai com a IA (spec §15). O DROP e' IF EXISTS
    porque `executescript` nao e' transacional: uma migracao interrompida e' reaplicada
    inteira na proxima subida, e a segunda passada nao pode levantar."""
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "m.db"))
    conn = db.get_conn()
    db.migrate(conn)
    tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "ia_chamadas" not in tabelas

    # Reaplicacao de verdade: apagar o registro e migrar de novo e' o cenario do
    # `executescript` interrompido. Um `db.migrate` extra sem isso apenas PULA o
    # arquivo (o nome ja esta em schema_migrations) e nao provaria nada sobre o DROP.
    conn.execute("DELETE FROM schema_migrations WHERE nome=?", ("010_remove_ia_chamadas.sql",))
    conn.commit()
    db.migrate(conn)          # DROP numa tabela que ja nao existe: nao pode levantar
    db.migrate(conn)          # e' idempotente rodando de novo
    assert "ia_chamadas" not in {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
