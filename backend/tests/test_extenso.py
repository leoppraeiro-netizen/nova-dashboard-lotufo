import pytest
from app import extenso

GABARITO = [
    (357854, "três mil, quinhentos e setenta e oito reais e cinquenta e quatro centavos"),
    (27850992, "duzentos e setenta e oito mil, quinhentos e nove reais e noventa e dois centavos"),
    (240892989, "dois milhões, quatrocentos e oito mil, novecentos e vinte e nove reais e oitenta e nove centavos"),
    (100000000, "um milhão de reais"),
    (1313, "treze reais e treze centavos"),
    # espelhos reais: " e " antes do ultimo grupo quando < 100 ou multiplo de 100; "," senao
    (5007415, "cinquenta mil e setenta e quatro reais e quinze centavos"),
    (86920018, "oitocentos e sessenta e nove mil e duzentos reais e dezoito centavos"),
    (3219258, "trinta e dois mil, cento e noventa e dois reais e cinquenta e oito centavos"),
    (174209879, "um milhão, setecentos e quarenta e dois mil e noventa e oito reais e setenta e nove centavos"),
    (30702, "trezentos e sete reais e dois centavos"),
    # bordas
    (10000, "cem reais"), (10100, "cento e um reais"), (100, "um real"), (1, "um centavo"),
    (45, "quarenta e cinco centavos"), (0, "zero reais"), (100000, "mil reais"), (100100, "mil e um reais"),
]


@pytest.mark.parametrize("centavos,texto", GABARITO)
def test_extenso(centavos, texto):
    assert extenso.reais(centavos) == texto


def test_negativo_e_acima_do_limite_recusam():
    with pytest.raises(ValueError):
        extenso.reais(-1)
    with pytest.raises(ValueError):
        extenso.reais(100_000_000_000)
