"""Montagem de PDF do protocolo (bloco 5).

Tetos do pacote. A montagem de verdade roda em `leitura_pdf.juntar_com_limite` (subprocesso com
limite e guarda de streams em cada parte), porque as pecas chegam de fora; `juntar` e `paginas` aqui
servem so' a PDF que o proprio sistema gerou (testes, paginas de titulo).
"""
import io

import pypdf

TETO_BYTES_PACOTE = 40 * 1024 * 1024     # a 42ª de Alta Floresta (SES) tem 10,9 MB e 114 paginas
TETO_PAGINAS_PACOTE = 400


def juntar(partes: list[bytes]) -> bytes:
    w = pypdf.PdfWriter()
    for p in partes:
        w.append(io.BytesIO(p))
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def paginas(pdf: bytes) -> int:
    return len(pypdf.PdfReader(io.BytesIO(pdf)).pages)
