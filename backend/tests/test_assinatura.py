"""Conferencia do PDF assinado (spec §6): paginas batem, extras so' certificado, carimbo em todas."""
from app import assinatura

G1 = "7E965481-0A1B-4C2D-8E9F-0123456789AB"
G2 = "C923C2B0-1111-2222-3333-444455556666"
MONTADO = ["CT/301/LT/2026 Cuiabá 16 de setembro Ref.: Contrato 099/2024 23ª Medição", "NOTA FISCAL 2311 valor 1.234,56", ""]


def _carimbar(paginas, guid=G1):
    return [f"Docusign Envelope ID: {guid}\n{t}" for t in paginas]


def test_assinado_certo_passa():
    r = assinatura.conferir(MONTADO, _carimbar(MONTADO))
    assert r["ok"] and r["envelope"] == G1 and r["avisos"] == []


def test_pdf_nao_assinado_e_pego():
    r = assinatura.conferir(MONTADO, MONTADO)
    assert not r["ok"] and [a["codigo"] for a in r["avisos"]] == ["nao_assinado"]


def test_pagina_trocada_e_pega():
    trocado = _carimbar([MONTADO[0], "OUTRA COISA COMPLETAMENTE DIFERENTE", ""])
    r = assinatura.conferir(MONTADO, trocado)
    assert any(a["codigo"] == "pagina_diferente" and "2" in a["mensagem"] for a in r["avisos"])


def test_certificado_no_fim_e_aceito_e_pagina_extra_qualquer_nao():
    cert = "Certificado de Conclusão\nIdentificação de envelope: " + G1
    r = assinatura.conferir(MONTADO, _carimbar(MONTADO) + [cert])
    assert r["ok"] and r["certificado"] == 1
    r = assinatura.conferir(MONTADO, _carimbar(MONTADO) + ["pagina solta"])
    assert [a["codigo"] for a in r["avisos"]] == ["paginas_extras"]


def test_pdfs_reais_do_docusign():
    """Textos por pagina de tres PDFs reais (tarefa 5.11): o CT-291 da Cavalaria (montado x assinado; paginas
    de planilha com o carimbo no fim do texto), o CT-073 da MT-388 (4 paginas + 4 de certificado, so' a
    primeira com o titulo) e o CT-286 da Orla, protocolado sem assinatura."""
    import json
    import pathlib
    fix = pathlib.Path(__file__).parent / "fixtures" / "assinatura"
    cav = json.loads((fix / "cavalaria-ct291.json").read_text(encoding="utf-8"))
    assert assinatura.conferir(cav["montado"], cav["assinado"])["ok"]
    trocado = cav["assinado"][:3] + [cav["assinado"][5]] + cav["assinado"][4:]
    assert [a["codigo"] for a in assinatura.conferir(cav["montado"], trocado)["avisos"]] == ["pagina_diferente"]
    ct073 = json.loads((fix / "mt388-ct073.json").read_text(encoding="utf-8"))["assinado"]
    r = assinatura.conferir([assinatura._ENVELOPE.sub("", t) for t in ct073[:4]], ct073)
    assert r["ok"] and r["certificado"] == 4
    ct286 = json.loads((fix / "orla-ct286.json").read_text(encoding="utf-8"))["assinado"]
    assert [a["codigo"] for a in assinatura.conferir(ct286, ct286)["avisos"]] == ["nao_assinado"]


def test_envelopes_diferentes_e_paginas_a_menos():
    misturado = _carimbar(MONTADO[:2]) + _carimbar(MONTADO[2:], G2)
    assert "envelopes_diferentes" in [a["codigo"] for a in assinatura.conferir(MONTADO, misturado)["avisos"]]
    assert "paginas_a_menos" in [a["codigo"] for a in assinatura.conferir(MONTADO, _carimbar(MONTADO[:2]))["avisos"]]
