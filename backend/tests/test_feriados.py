import datetime

from app import feriados

D = datetime.date


def test_pascoa_e_paixao():
    assert feriados.pascoa(2026) == D(2026, 4, 5)
    assert feriados.pascoa(2027) == D(2027, 3, 28)
    assert D(2026, 4, 3) in feriados.nacionais(2026)          # Paixao de Cristo


def test_consciencia_negra_so_a_partir_de_2024():
    assert D(2026, 11, 20) in feriados.nacionais(2026)
    assert D(2023, 11, 20) not in feriados.nacionais(2023)


def test_falencias_reais_do_backup():
    # emissao conta como 1o dia; sem feriado no meio, igual a antiga
    assert feriados.somar_dias_uteis(D(2026, 7, 13), 30) == D(2026, 8, 21)
    assert feriados.somar_dias_uteis(D(2026, 6, 17), 30) == D(2026, 7, 28)
    # Corpus Christi (04/06/2026) e' ponto facultativo: conta como dia util
    assert feriados.somar_dias_uteis(D(2026, 5, 14), 30) == D(2026, 6, 24)
    # 07/09 e' feriado: a antiga gravou 11/09, o certo e' 14/09
    assert feriados.somar_dias_uteis(D(2026, 8, 3), 30) == D(2026, 9, 14)


def test_emissao_no_fim_de_semana_comeca_na_segunda():
    assert feriados.somar_dias_uteis(D(2026, 8, 1), 1) == D(2026, 8, 3)
