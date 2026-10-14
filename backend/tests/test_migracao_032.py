"""Migracao 032 (FRC) e as sementes das migracoes antigas sem dado real (issue #110).

A configuracao da FRC de cada consorcio (prestador, tomador, e-mails, descricao, consorciadas) vem do cadastro
(`frc.yaml`), por `cadastro aplicar`; a migracao so' cria a estrutura. A producao ja' tem as linhas que a 032
semeava antes: reaplicar a migracao nao pode apagar nem sobrescrever o que esta' no banco.
"""
import json

import pytest

from app import db
from tests import ficticios

# Exercita a propria migracao: parte de um banco vazio de verdade, sem o banco-modelo do conftest.
pytestmark = pytest.mark.migracao_real


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    yield c
    c.close()


def test_banco_novo_nao_traz_frc_semeada(conn):
    assert conn.execute("SELECT COUNT(*) FROM frc_consorcios").fetchone()[0] == 0


def test_reaplicar_032_nao_sobrescreve_o_que_ja_esta_no_banco(conn):
    """O banco da producao tem a FRC com os destinatarios reais: a 032 reexecutada nao mexe na linha."""
    dados = {"logo": None, "prestador": {"email": "consorcio@exemplo.com.br"},
             "tomador": {"email": "fiscal@exemplo.gov.br"}, "descricao": {}, "consorciadas": []}
    conn.execute("INSERT INTO frc_consorcios (consorcio, formulario, ultimo_anterior, dados, atualizado_em) "
                 "VALUES ('integra-brt', 'A', 21, ?, '2026-10-09 10:00:00')", (json.dumps(dados),))
    conn.execute("DELETE FROM schema_migrations WHERE nome='032_frc.sql'"); conn.commit()
    db.migrate(conn)
    assert [tuple(r) for r in conn.execute(
        "SELECT consorcio, formulario, ultimo_anterior, dados, atualizado_em FROM frc_consorcios")] == [
        ("integra-brt", "A", 21, json.dumps(dados), "2026-10-09 10:00:00")]


def test_reaplicar_006_nao_mexe_na_empresa_propria_ja_gravada(conn):
    """A producao tem a entidade 1 com o CNPJ real (gravado pela 006 antiga e reivindicado pelo cadastro): a 006
    reexecutada com o CNPJ ficticio nao sobrescreve nada."""
    conn.execute("UPDATE entidades SET cnpj='31201111000190', nome='Empresa Propria Gravada', chave='lotufo', "
                 "sigla_oficio='EP', coligada_rm=1 WHERE id=1")
    antes = dict(conn.execute("SELECT * FROM entidades WHERE id=1").fetchone())
    conn.execute("DELETE FROM schema_migrations WHERE nome='006_certidoes.sql'"); conn.commit()
    db.migrate(conn)
    assert dict(conn.execute("SELECT * FROM entidades WHERE id=1").fetchone()) == antes
    assert conn.execute("SELECT COUNT(*) FROM entidades").fetchone()[0] == 1


def test_sementes_das_migracoes_sem_dado_real(conn):
    """A empresa propria semeada (006) tem CNPJ ficticio (o real entra pelo cadastro) e os padroes da deteccao
    antiga (014, arquivada pela 027), e-mail de exemplo."""
    assert conn.execute("SELECT cnpj FROM entidades WHERE id=1").fetchone()[0] == ficticios.LOTUFO
    valores = [r[0] for r in conn.execute("SELECT valor FROM arquivo_deteccao_padroes")]
    assert valores and all("exemplo.com.br" in v for v in valores)
