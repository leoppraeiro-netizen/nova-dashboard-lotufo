"""Migracao 037: o CHECK de `pleito_anexos.tipo` aceita as pecas do pleito de reajuste (issue #50) e a reconstrucao
da tabela preserva os anexos que ja' estavam no banco."""
import sqlite3

import pytest

from app import db

pytestmark = pytest.mark.migracao_real


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    c.execute("PRAGMA foreign_keys=OFF")     # anexo solto, sem montar pleito e contrato: o teste e' do CHECK
    yield c
    c.close()


def _anexo(conn, tipo):
    conn.execute("INSERT INTO pleito_anexos (pleito_id, tipo, nome, arquivo, sha256, tamanho, ext) "
                 "VALUES (1, ?, 'a.pdf', 'pleitos/a.pdf', 'abc', 10, 'pdf')", (tipo,))


def test_037_aceita_as_pecas_e_recusa_tipo_desconhecido(conn):
    for tipo in ("falencia", "contrato_social", "documento_representante", "balanco"):
        _anexo(conn, tipo)
    with pytest.raises(sqlite3.IntegrityError):
        _anexo(conn, "inventado")


def test_reaplicar_037_preserva_os_anexos(conn):
    _anexo(conn, "cronograma"); _anexo(conn, "balanco")
    conn.execute("UPDATE pleito_anexos SET removido_em='2026-10-01 10:00:00' WHERE tipo='cronograma'")
    antes = [tuple(r) for r in conn.execute("SELECT * FROM pleito_anexos ORDER BY id")]
    conn.execute("DELETE FROM schema_migrations WHERE nome='037_pleito_anexos_pecas.sql'"); conn.commit()
    db.migrate(conn)
    assert [tuple(r) for r in conn.execute("SELECT * FROM pleito_anexos ORDER BY id")] == antes
