"""Politica de fuso (divida estrutural #2 da fase 2).

O banco grava UTC; o NEGOCIO decide em America/Cuiaba. Estes testes pinam
exatamente a fronteira onde as duas leituras discordam.
"""
import datetime

from app import tempo


def test_mes_local_virada_de_mes():
    # 31/08 21:30 local = 01/09 01:30 UTC: o mes de negocio ainda e agosto.
    assert tempo.mes_local("2026-09-01 01:30:00") == "2026-08"
    assert tempo.mes_local("2026-09-01 05:30:00") == "2026-09"  # ja passou da meia-noite local


def test_para_local_offset():
    d = tempo.para_local(tempo.agora_utc())
    assert d.utcoffset().total_seconds() == -4 * 3600  # Cuiaba = UTC-4, sem DST desde 2019


def test_mes_local_aceita_iso_com_t_e_z():
    """O banco grava 'AAAA-MM-DD HH:MM:SS', mas ISO com 'T'/'Z' circula pela API."""
    assert tempo.mes_local("2026-09-01T01:30:00") == "2026-08"
    assert tempo.mes_local("2026-09-01T01:30:00Z") == "2026-08"


def test_para_local_trata_ingenuo_como_utc():
    """Datetime sem tzinfo vem do banco -- e o banco so grava UTC."""
    ingenuo = datetime.datetime(2026, 9, 1, 1, 30, 0)
    assert tempo.para_local(ingenuo).strftime("%Y-%m-%d %H:%M") == "2026-08-31 21:30"


def test_agora_utc_e_aware_em_utc():
    assert tempo.agora_utc().utcoffset() == datetime.timedelta(0)


def test_hoje_local_e_a_data_de_cuiaba():
    assert tempo.hoje_local() == tempo.para_local(tempo.agora_utc()).date()
