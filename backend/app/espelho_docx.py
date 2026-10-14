"""Preenche content controls (w:sdt) de um modelo .docx pelo `w:tag` (spec §4.2, modelos Word).

O .docx e' um zip; so' `word/document.xml` muda. lxml preserva prefixos de namespace (o
`mc:Ignorable` do Word referencia prefixos pelo nome; ElementTree os renomearia). O zip de saida
e' regravado com data fixa e ordem estavel para o mesmo conteudo dar o mesmo sha256.
"""
import io
import zipfile

from lxml import etree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{%s}" % NS["w"]
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_DATA_FIXA = (1980, 1, 1, 0, 0, 0)


class DocxInvalido(Exception):
    pass


def _document(docx: bytes) -> tuple[zipfile.ZipFile, etree._Element]:
    try:
        z = zipfile.ZipFile(io.BytesIO(docx))
        xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise DocxInvalido("arquivo não é um .docx com word/document.xml") from e
    try:
        return z, etree.fromstring(xml)
    except etree.XMLSyntaxError as e:
        raise DocxInvalido(f"document.xml malformado: {e}") from e


def _tag(sdt) -> str | None:
    t = sdt.find(f"{W}sdtPr/{W}tag")
    return None if t is None else t.get(f"{W}val")


def _preenchivel(sdt) -> bool:
    """So' conta o controle que `preencher` consegue preencher: com sdtContent e ao menos um w:t."""
    conteudo = sdt.find(f"{W}sdtContent")
    return conteudo is not None and conteudo.find(f".//{W}t") is not None


def controles(docx: bytes) -> set[str]:
    _, raiz = _document(docx)
    return {t for t in (_tag(s) for s in raiz.iter(f"{W}sdt") if _preenchivel(s)) if t}


def preencher(docx: bytes, valores: dict[str, str]) -> bytes:
    z, raiz = _document(docx)
    for sdt in raiz.iter(f"{W}sdt"):
        tag = _tag(sdt)
        if tag not in valores or not _preenchivel(sdt):
            continue
        conteudo = sdt.find(f"{W}sdtContent")
        primeiro_t = conteudo.find(f".//{W}t")
        run = primeiro_t.getparent()
        # o texto inteiro vai no primeiro run (mantem a formatacao dele, rPr); tudo o mais que
        # estava no placeholder -- outros runs, quebras, tabs, desenhos -- sai, senao o valor
        # novo apareceria colado ao resto do texto antigo
        primeiro_t.text = valores[tag]
        primeiro_t.set(_XML_SPACE, "preserve")
        for filho in list(run):
            if filho is not primeiro_t and filho.tag != f"{W}rPr":
                run.remove(filho)
        pai = run.getparent()
        for irmao in list(pai):
            if irmao is not run and irmao.tag != f"{W}pPr":
                pai.remove(irmao)
        # placeholder do Word ("Clique para digitar") deixaria o texto cinza
        ph = sdt.find(f"{W}sdtPr/{W}showingPlcHdr")
        if ph is not None:
            ph.getparent().remove(ph)
    novo_xml = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as saida:
        for info in sorted(z.infolist(), key=lambda i: i.filename):
            dados = novo_xml if info.filename == "word/document.xml" else z.read(info.filename)
            zi = zipfile.ZipInfo(info.filename, date_time=_DATA_FIXA)
            zi.compress_type = zipfile.ZIP_DEFLATED
            saida.writestr(zi, dados)
    return buf.getvalue()
