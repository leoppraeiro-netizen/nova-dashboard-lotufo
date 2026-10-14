import pathlib

import pytest

from app import leitura_certidao as lc

FIX = pathlib.Path(__file__).parent / "fixtures" / "certidoes"
CADASTRADOS = frozenset({"31200101000130", "31200606000102", "31200202000100", "31200707000175",
                         "31200303000181", "31200404000152", "31200505000123"})


def _ler(nome):
    return lc.ler((FIX / f"{nome}.txt").read_text(encoding="utf-8"), CADASTRADOS)


@pytest.mark.parametrize("nome, tipo, natureza, cnpj, emissao, validade, numero", [
    ("federal-alfa", "federal", "positiva_efeito_negativa", "31200101000130", "2026-06-24", "2026-12-21", "A1B2.C3D4.E5F6.0718"),
    ("federal-epsilon", "federal", "negativa", "31200505000123", "2026-08-03", "2027-01-30", "B2C3.D4E5.F607.1829"),
    ("fgts-alfa", "fgts", "negativa", "31200101000130", "2026-07-11", "2026-08-09", "2026071109560111223344"),
    ("fgts-gama", "fgts", "negativa", "31200303000181", "2026-07-28", "2026-08-26", "2026072807571122334455"),
    ("trabalhista-alfa", "trabalhista", "negativa", "31200101000130", "2026-06-24", "2026-12-21", "99100001/2026"),
    ("estadual-alfa", "estadual", "positiva_efeito_negativa", "31200101000130", "2026-06-24", "2026-08-22", "7ZZ1QK3M8T5N2R4B"),
    ("estadual-gama", "estadual", "negativa", "31200303000181", "2026-06-24", "2026-08-22", "9QPL4KX7TW3MB6ZC"),
    ("municipal-alfa", "municipal", "positiva_efeito_negativa", "31200101000130", "2026-06-24", "2026-07-24", "992222/2026"),
    ("municipal-delta", "municipal", "negativa", "31200404000152", "2026-07-07", "2026-10-05", "991111/2026"),
    ("falencia-alfa", "falencia", "negativa", "31200101000130", "2026-07-13", "2026-08-21", "99200002"),
    ("falencia-delta", "falencia", "negativa", "31200404000152", "2026-08-03", "2026-09-14", "99200001"),
])
def test_certidoes_reais(nome, tipo, natureza, cnpj, emissao, validade, numero):
    r = _ler(nome)
    assert (r["tipo"], r["natureza"], r["cnpj"], r["emissao"], r["validade"], r["numero"]) == \
        (tipo, natureza, cnpj, emissao, validade, numero)
    assert r["validade_calculada"] is (tipo == "falencia")


def test_estadual_positiva_pura_e_recusada():
    with pytest.raises(lc.Recusa) as e:
        _ler("estadual-beta-cpd")
    assert e.value.motivo == "positiva" and "positiva" not in lc.DIGITAVEIS


def test_texto_curto_e_sem_texto():
    with pytest.raises(lc.Recusa) as e:
        lc.ler("   ")
    assert e.value.motivo == "sem-texto" and e.value.motivo in lc.DIGITAVEIS


def test_documento_que_nao_e_certidao():
    with pytest.raises(lc.Recusa) as e:
        lc.ler("NOTA FISCAL DE SERVICOS ELETRONICA " * 5)
    assert e.value.motivo == "tipo-desconhecido"


def test_cnpj_do_cadastro_vence_o_primeiro_do_texto():
    texto = (FIX / "municipal-alfa.txt").read_text(encoding="utf-8")
    assert "10200300431.200.101/0001-30" in texto        # inscricao estadual colada no CNPJ
    assert lc.ler("CNPJ 11.444.777/0001-61 " + texto, CADASTRADOS)["cnpj"] == "31200101000130"


def test_normalizacao_desfaz_ligadura_e_espaco_nao_quebravel():
    assert lc.plano("Certiﬁcado de  Regularidade") == "CERTIFICADO DE REGULARIDADE"
    assert lc.plano("Certi fi cado") == "CERTIFICADO"
