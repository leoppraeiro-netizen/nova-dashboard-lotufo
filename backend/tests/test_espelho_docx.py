import io
import zipfile

import pytest
from app import espelho_docx

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def sdt(tag, texto):
    return (f'<w:sdt><w:sdtPr><w:alias w:val="{tag}"/><w:tag w:val="{tag}"/><w:id w:val="5001"/></w:sdtPr>'
            f'<w:sdtContent><w:r><w:rPr><w:b/></w:rPr><w:t>{texto[:3]}</w:t></w:r>'
            f'<w:r><w:t>{texto[3:]}</w:t></w:r></w:sdtContent></w:sdt>')


def docx_com(corpo_xml: str) -> bytes:
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W} '
           'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="w14">'
           f'<w:body>{corpo_xml}</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
                                           'package/2006/content-types"/>')
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", "<a/>")
    return buf.getvalue()


def docx_minimo() -> bytes:
    return docx_com(f'<w:p><w:r><w:t>VALOR DA MEDIÇÃO: R$ </w:t></w:r>{sdt("valor", "1.000,00")}</w:p>'
                    f'<w:p>{sdt("medicao", "9ª")}<w:r><w:t> fixo </w:t></w:r>{sdt("valor", "1.000,00")}</w:p>')


def texto_de(docx: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        return z.read("word/document.xml").decode("utf-8")


def test_controles_lista_as_tags():
    assert espelho_docx.controles(docx_minimo()) == {"valor", "medicao"}


def test_preencher_troca_todas_as_ocorrencias_e_preserva_o_resto():
    saida = espelho_docx.preencher(docx_minimo(), {"valor": "278.509,92", "medicao": "23ª", "inexistente": "x"})
    xml = texto_de(saida)
    assert xml.count("278.509,92") == 2 and "23ª" in xml and "1.000,00" not in xml and "9ª" not in xml
    assert "VALOR DA MEDIÇÃO: R$ " in xml and "<w:b/>" in xml and 'mc:Ignorable="w14"' in xml
    with zipfile.ZipFile(io.BytesIO(saida)) as z:
        assert z.read("word/styles.xml") == b"<a/>"


def test_preencher_e_deterministico_para_o_hash():
    a = espelho_docx.preencher(docx_minimo(), {"valor": "1,00"})
    b = espelho_docx.preencher(docx_minimo(), {"valor": "1,00"})
    assert a == b


def test_docx_sem_document_xml_e_recusado():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.txt", "nada")
    with pytest.raises(espelho_docx.DocxInvalido):
        espelho_docx.controles(buf.getvalue())


def test_controle_sem_texto_nao_conta_como_preenchivel():
    vazio = ('<w:sdt><w:sdtPr><w:tag w:val="mo"/></w:sdtPr><w:sdtContent><w:r><w:br/></w:r></w:sdtContent></w:sdt>')
    docx = docx_com(f'<w:p>{sdt("valor", "1,00")}{vazio}</w:p>')
    assert espelho_docx.controles(docx) == {"valor"}


def test_preencher_remove_quebras_e_runs_extras_do_placeholder():
    placeholder = ('<w:sdt><w:sdtPr><w:tag w:val="valor"/></w:sdtPr><w:sdtContent>'
                   '<w:r><w:rPr><w:b/></w:rPr><w:t>1.0</w:t><w:br/></w:r><w:r><w:t>00,00</w:t></w:r>'
                   '<w:r><w:tab/><w:t>lixo</w:t></w:r></w:sdtContent></w:sdt>')
    xml = texto_de(espelho_docx.preencher(docx_com(f"<w:p>{placeholder}</w:p>"), {"valor": "2,00"}))
    assert xml.count("<w:t ") + xml.count("<w:t>") == 1 and "2,00" in xml and "lixo" not in xml
    assert "<w:br/>" not in xml and "<w:tab/>" not in xml and "<w:b/>" in xml
