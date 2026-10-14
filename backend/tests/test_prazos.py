"""Prazo do contrato (spec §7.3 e §7.4): execucao, vigencia, folga, paralisacao, endosso, encerramento."""
import datetime
import json

import pytest

from app import auth, db, prazos

D = datetime.date


@pytest.fixture
def cenario(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@l.com", "senha-forte-123", "admin")
    for chave, auto in (("sinfra-x", True), ("mtpar", False)):
        c.execute("INSERT INTO orgaos (chave, nome, familia, regras) VALUES (?, ?, ?, ?)",
                  (chave, chave.upper(), "sinfra" if chave == "sinfra-x" else "mtpar",
                   json.dumps({"vigencia_automatica": auto, "folga_vigencia_dias": 90})))
    c.execute("INSERT INTO contratos (orgao, numero_instrumento, nome_curto, objeto, valor_original_centavos, orgao_id, "
              "execucao_fim, vigencia_fim) VALUES ('SINFRA', 'IC 1/2026', 'Obra A', 'obra', 100, "
              "(SELECT id FROM orgaos WHERE chave='sinfra-x'), '2026-10-20', '2027-01-20')")
    cid = c.execute("SELECT MAX(id) FROM contratos").fetchone()[0]
    c.commit()

    def aditivo(data, nova_exe, nova_vig, forma="termo_aditivo", numero="001/2026", chave="ta-1"):
        c.execute("INSERT INTO aditivos (contrato_id, tipo, delta_valor_centavos, nova_execucao_fim, nova_vigencia_fim, "
                  "status, data_assinatura, numero, forma, chave_cadastro) VALUES (?, 'prazo', 0, ?, ?, 'assinado', ?, ?, ?, ?)",
                  (cid, nova_exe, nova_vig, data, numero, forma, chave))
        c.commit()

    def instrumento(tipo, data, dados=None, chave=None):
        c.execute("INSERT INTO instrumentos (contrato_id, chave, tipo, data, dados) VALUES (?, ?, ?, ?, ?)",
                  (cid, chave or f"{tipo}-{data}", tipo, data, json.dumps(dados or {})))
        c.commit()

    def pleito(tipo, enviado_em, oficio="CT-310-LT-2026"):
        c.execute("INSERT INTO pleitos (contrato_id, tipo, origem, numero_oficio, situacao, enviado_em) "
                  "VALUES (?, ?, 'cadastro', ?, 'enviado', ?)", (cid, tipo, oficio, enviado_em))
        c.commit()

    yield c, {"contrato": cid, "aditivo": aditivo, "instrumento": instrumento, "pleito": pleito}
    c.close()


def _por_tipo(c, hoje):
    return {a["tipo"]: a for a in prazos.avisos(c, hoje)}


def test_execucao_60_30_e_vencida_sem_pedido_vai_para_a_diretoria(cenario):
    c, _ = cenario
    assert _por_tipo(c, D(2026, 9, 1))["execucao_vencendo"]["nivel"] == "atencao"
    assert _por_tipo(c, D(2026, 10, 1))["execucao_vencendo"]["nivel"] == "critico"
    a = _por_tipo(c, D(2026, 10, 25))["instrumento_pendente"]
    assert (a["nivel"], a["publico"]) == ("critico", ["operacao", "diretoria"]) and "sem pedido" in a["mensagem"]


def test_pedido_enviado_troca_o_aviso_e_instrumento_posterior_fecha(cenario):
    c, ids = cenario
    ids["pleito"]("prazo", "2026-09-05")
    a = _por_tipo(c, D(2026, 9, 10))
    assert "execucao_vencendo" not in a and a["instrumento_pendente"]["nivel"] == "atencao"
    assert "pedida em 05/09/2026" in a["instrumento_pendente"]["mensagem"]
    ids["aditivo"]("2026-09-20", "2027-01-20", "2027-04-20")
    assert not {"execucao_vencendo", "instrumento_pendente"} & set(_por_tipo(c, D(2026, 9, 25)))


def test_resumo_para_a_lista_de_obras(cenario):
    c, ids = cenario                  # A9: dias ate' o fim e o pedido em curso, que o instrumento fecha
    r = prazos.resumo(c, ids["contrato"], D(2026, 9, 10))
    assert (r["dias_execucao"], r["dias_vigencia"], r["vigencia_automatica"], r["pedido_prorrogacao"]) == (40, 132, True, None)
    ids["pleito"]("prazo", "2026-09-05")
    assert prazos.resumo(c, ids["contrato"], D(2026, 9, 10))["pedido_prorrogacao"] == {
        "enviado_em": "2026-09-05", "numero_oficio": "CT-310-LT-2026", "dias": 5}
    ids["aditivo"]("2026-09-20", "2027-01-20", "2027-04-20")
    assert prazos.resumo(c, ids["contrato"], D(2026, 9, 25))["pedido_prorrogacao"] is None


def test_paralisacao_aberta_suspende_o_aviso_e_avisa_operacao_e_diretoria(cenario):
    c, ids = cenario
    ids["instrumento"]("paralisacao", "2026-02-01")
    a = _por_tipo(c, D(2026, 10, 1))
    assert "execucao_vencendo" not in a and a["obra_paralisada"]["publico"] == ["operacao", "diretoria"]
    assert (a["obra_paralisada"]["data"], a["obra_paralisada"]["sentido"]) == ("2026-02-01", "desde")
    ids["instrumento"]("reinicio", "2026-05-05")
    a = _por_tipo(c, D(2026, 10, 1))
    assert "obra_paralisada" not in a and "execucao_vencendo" in a


def test_folga_quebrada_pelo_contrato_e_pelo_orgao(cenario):
    c, ids = cenario
    c.execute("UPDATE contratos SET execucao_fim='2026-12-01', vigencia_fim='2027-01-15'"); c.commit()
    a = _por_tipo(c, D(2026, 9, 1))["folga_quebrada"]
    assert a["nivel"] == "acao" and "folga de 45 dias, o órgão pede 90" in a["mensagem"]
    c.execute("UPDATE contratos SET folga_vigencia_dias=30"); c.commit()
    assert "folga_quebrada" not in _por_tipo(c, D(2026, 9, 1))


def test_vigencia_so_sem_prorrogacao_automatica(cenario):
    c, _ = cenario
    assert "vigencia_vencendo" not in _por_tipo(c, D(2026, 12, 1))
    c.execute("UPDATE contratos SET orgao_id=(SELECT id FROM orgaos WHERE chave='mtpar')"); c.commit()
    assert _por_tipo(c, D(2026, 12, 1))["vigencia_vencendo"]["dias"] == 50


def test_endosso_ate_5_dias_atencao_depois_acao_e_endosso_fecha(cenario):
    c, ids = cenario
    ids["aditivo"]("2026-09-20", "2027-01-20", "2027-04-20")
    a = _por_tipo(c, D(2026, 9, 23))["endosso_garantia"]
    assert a["nivel"] == "atencao" and "vence em 2 dias" in a["mensagem"]
    a = _por_tipo(c, D(2026, 9, 28))["endosso_garantia"]
    assert a["nivel"] == "acao" and "atrasado 3 dias" in a["mensagem"]
    ids["instrumento"]("endosso_garantia", "2026-09-19", {"referente": "ta-1"})
    assert "endosso_garantia" not in _por_tipo(c, D(2026, 9, 28))


def test_endosso_nao_cobra_instrumento_antigo(cenario):
    c, ids = cenario
    ids["aditivo"]("2026-06-01", "2027-01-20", "2027-04-20")
    assert "endosso_garantia" not in _por_tipo(c, D(2026, 9, 1))


def test_retroativo_sinalizado(cenario):
    c, ids = cenario
    c.execute("UPDATE contratos SET execucao_fim='2026-02-28'"); c.commit()
    ids["aditivo"]("2026-03-10", "2026-08-31", None)
    assert prazos.situacao(c, ids["contrato"], D(2026, 3, 15))["instrumentos"][0]["retroativo"] is True


def test_em_encerramento_so_conclusao_nao_comunicada(cenario):
    c, ids = cenario
    c.execute("UPDATE contratos SET encerramento_iniciado_em='2026-09-01'"); c.commit()
    a = prazos.avisos(c, D(2026, 10, 15))
    assert [(x["tipo"], x["nivel"], x["dias"]) for x in a] == [("conclusao_nao_comunicada", "acao", 44)]
    ids["pleito"]("conclusao", "2026-10-16", "CT-400-LT-2026")
    assert prazos.avisos(c, D(2026, 10, 20)) == []


def test_historico_texto_ordinal_por_forma(cenario):
    c, ids = cenario
    ids["aditivo"]("2025-03-10", "2025-10-20", "2026-01-18", numero="001/2025", chave="ta-1")
    ids["aditivo"]("2025-09-01", "2026-10-20", None, forma="apostilamento", numero="002/2025", chave="ap-1")
    texto = prazos.historico_texto(c, ids["contrato"])
    assert ("O 1º termo aditivo n.º 001/2025 foi assinado em 10/03/2025, com término da execução em 20/10/2025 "
            "e da vigência em 18/01/2026.") in texto
    assert "O 1º termo de apostilamento n.º 002/2025 foi assinado em 01/09/2025" in texto
