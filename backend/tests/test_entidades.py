import pytest
from app import auditoria, auth, db, entidades

# CNPJs SINTETICOS com DV valido (conferidos em entidades.cnpj_valido); nenhum e' de
# empresa real — dado de teste nao carrega CNPJ de terceiro.
CNPJ_OK = "11444777000161"
CNPJ_OK2 = "31201111000190"
CNPJ_DV_ERRADO = "11444777000160"   # mesmo base de CNPJ_OK, ultimo DV trocado (1 -> 0)


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@l.com", "senha-forte-123", "admin")
    yield c
    c.close()


@pytest.mark.migracao_real      # a semente da migracao de verdade, nao o banco-modelo com o CNPJ ficticio do conftest
def test_lotufo_vem_semeada(conn):
    lotufo = [e for e in entidades.listar(conn) if e["papel"] == "lotufo"]
    assert len(lotufo) == 1
    assert lotufo[0]["id"] == 1 and len(lotufo[0]["cnpj"]) == 14
    assert entidades.cnpj_valido(lotufo[0]["cnpj"])   # o seed nao burla a propria regra


def test_criar_e_listar(conn):
    eid = entidades.criar(conn, 1, {"nome": "Consórcio Norte", "cnpj": CNPJ_OK,
                                    "papel": "consorcio"})
    e = [x for x in entidades.listar(conn) if x["id"] == eid][0]
    assert e["nome"] == "Consórcio Norte" and e["papel"] == "consorcio" and e["ativo"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM audit_log WHERE acao='entidade.criar'"
                        ).fetchone()["c"] == 1
    assert auditoria.verificar_cadeia(conn)


def test_cnpj_aceita_mascara_e_normaliza_para_14_digitos(conn):
    eid = entidades.criar(conn, 1, {"nome": "Consorciada Sul", "cnpj": "31.201.111/0001-90",
                                    "papel": "consorciada"})
    assert entidades.detalhe(conn, eid)["cnpj"] == CNPJ_OK2


def test_dv_invalido_rejeita(conn):
    with pytest.raises(ValueError, match="CNPJ inválido"):
        entidades.criar(conn, 1, {"nome": "X", "cnpj": CNPJ_DV_ERRADO, "papel": "consorciada"})
    # nem a entidade nem a linha de auditoria entram
    assert conn.execute("SELECT COUNT(*) c FROM entidades").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"] == 0


def test_cnpj_curto_ou_com_letra_rejeita(conn):
    for ruim in ("1144477700016", "1144477700016X", "", None):
        with pytest.raises(ValueError, match="CNPJ inválido"):
            entidades.criar(conn, 1, {"nome": "X", "cnpj": ruim, "papel": "consorciada"})


def test_cnpj_de_digitos_repetidos_rejeita(conn):
    # 00000000000000 e 11111111111111 PASSAM no modulo 11 e nao sao CNPJ de ninguem:
    # sem esta guarda, o DV sozinho os aceitaria.
    for ruim in ("00000000000000", "11111111111111", "99999999999999"):
        with pytest.raises(ValueError, match="CNPJ inválido"):
            entidades.criar(conn, 1, {"nome": "X", "cnpj": ruim, "papel": "consorciada"})


def test_dv_valido_nos_dois_digitos(conn):
    assert entidades.cnpj_valido(CNPJ_OK)
    assert entidades.cnpj_valido(CNPJ_OK2)
    assert not entidades.cnpj_valido(CNPJ_DV_ERRADO)
    assert not entidades.cnpj_valido("11444777000171")   # primeiro DV trocado (6 -> 7)


def test_papel_invalido_rejeita(conn):
    with pytest.raises(ValueError, match="Papel inválido"):
        entidades.criar(conn, 1, {"nome": "X", "cnpj": CNPJ_OK, "papel": "matriz"})


def test_nome_vazio_rejeita(conn):
    with pytest.raises(ValueError, match="Nome"):
        entidades.criar(conn, 1, {"nome": "   ", "cnpj": CNPJ_OK, "papel": "consorcio"})


def test_cnpj_duplicado_rejeita(conn):
    entidades.criar(conn, 1, {"nome": "Consórcio Norte", "cnpj": CNPJ_OK, "papel": "consorcio"})
    with pytest.raises(ValueError, match="já cadastrado"):
        entidades.criar(conn, 1, {"nome": "Outro nome", "cnpj": CNPJ_OK, "papel": "consorciada"})
    # tambem com mascara: a unicidade e' sobre os 14 digitos, nao sobre a string digitada
    with pytest.raises(ValueError, match="já cadastrado"):
        entidades.criar(conn, 1, {"nome": "Outro", "cnpj": "11.444.777/0001-61",
                                  "papel": "consorciada"})
    assert conn.execute("SELECT COUNT(*) c FROM entidades").fetchone()["c"] == 2


def test_desativar(conn):
    eid = entidades.criar(conn, 1, {"nome": "Consórcio Velho", "cnpj": CNPJ_OK,
                                    "papel": "consorcio"})
    entidades.desativar(conn, 1, eid)
    assert eid not in [e["id"] for e in entidades.listar(conn)]
    assert eid in [e["id"] for e in entidades.listar(conn, ativas=False)]
    assert entidades.detalhe(conn, eid)["ativo"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM audit_log WHERE acao='entidade.desativar'"
                        ).fetchone()["c"] == 1
    assert auditoria.verificar_cadeia(conn)


def test_desativar_duas_vezes_rejeita(conn):
    eid = entidades.criar(conn, 1, {"nome": "C", "cnpj": CNPJ_OK, "papel": "consorcio"})
    entidades.desativar(conn, 1, eid)
    with pytest.raises(ValueError, match="já está desativada"):
        entidades.desativar(conn, 1, eid)


def test_desativar_com_contrato_ativo_rejeita(conn):
    """Achado 6 do gate 3. A entidade desativada sai de `listar` -- e sai do painel de
    certidoes e do checklist de protocolo, que percorrem as ativas. O contrato
    continuaria vivo cobrando certidoes de um CNPJ que a tela nao mostra mais."""
    from app import contratos
    eid = entidades.criar(conn, 1, {"nome": "Consórcio Norte", "cnpj": CNPJ_OK,
                                    "papel": "consorcio"})
    cid = contratos.criar(conn, 1, {"orgao": "SINFRA", "numero_instrumento": "IC 3/2026",
                                    "objeto": "Obra X", "valor_original_centavos": 100,
                                    "entidade_id": eid})
    with pytest.raises(ValueError, match="IC 3/2026"):
        entidades.desativar(conn, 1, eid)
    assert entidades.detalhe(conn, eid)["ativo"] == 1
    # suspenso nao segura a desativacao: o que a trava e' contrato EM EXECUCAO
    contratos.mudar_estado(conn, 1, cid, "suspenso", "2026-09-01", None)
    entidades.desativar(conn, 1, eid)
    assert entidades.detalhe(conn, eid)["ativo"] == 0


def test_desativar_inexistente_rejeita(conn):
    with pytest.raises(ValueError, match="não encontrada"):
        entidades.desativar(conn, 1, 999)
    assert not conn.in_transaction
