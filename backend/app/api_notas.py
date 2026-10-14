"""Nota fiscal na medicao (spec §3 passo 3, §7.1): anexar PDF, digitar quando nao le, declarar completo,
vincular nota do RM, justificar divergencia."""
import datetime
import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import arquivos, dinheiro, frc, leitura_pdf, medicoes, notas, sincronizacao_rm
from app.api_auth import conexao
from app.api_medicoes import ID, MAX_INT64, _erro_do_cliente, _medicao_existe
from app.permissoes import exigir

router = APIRouter()


class ManualIn(BaseModel):
    documento_id: int = Field(ge=1, le=MAX_INT64)
    numero: int = Field(ge=1, le=999_999_999)
    emissao: datetime.date
    valor: str = Field(min_length=1, max_length=40)


class JustificativaIn(BaseModel):
    justificativa: str = Field(min_length=1, max_length=1000)


def _bytes_validados(arquivo: UploadFile) -> bytes:
    """Tipo, `%PDF-` e teto de 10 MB (415/413, como o upload de certidao)."""
    return b"".join(arquivos.blocos_validados(arquivo))


@router.get("/api/medicoes/{medicao_id}/notas")
def listar(medicao_id: ID, _=Depends(exigir("ver_paineis", com_csrf=False)),
           conn: sqlite3.Connection = Depends(conexao)):
    _medicao_existe(conn, medicao_id)
    m = medicoes.detalhe(conn, medicao_id)
    # PDFs de nota anexados que ainda nao viraram nota (sem texto / leiaute desconhecido e a pessoa
    # nao digitou na hora): continuam a' espera dos dados, tambem depois de recarregar a tela. A nota de
    # consorciada LIDA (migracao 032 guarda a leitura) nao vira nota fiscal e nao espera nada: fica de fora.
    sem_nota = [dict(r) for r in conn.execute("""
        SELECT d.id AS documento_id, d.nome FROM medicao_documentos d
        WHERE d.medicao_id=? AND d.tipo_doc='nfs' AND d.fonte='operacao'
          AND (d.leitura IS NULL OR json_extract(d.leitura, '$.ok') IS NOT 1)
          AND NOT EXISTS (SELECT 1 FROM notas_fiscais n WHERE n.documento_id=d.id) ORDER BY d.id""", (medicao_id,))]
    return {"esperadas": notas.esperadas(conn, medicao_id),
            "notas": sincronizacao_rm.notas_da_medicao(conn, medicao_id),
            "faltam": notas.faltam(conn, medicao_id),
            "documentos_sem_nota": sem_nota,
            "pode_declarar": m["estado"] in medicoes.ESTADOS_ESPELHO}


@router.post("/api/medicoes/{medicao_id}/notas", status_code=201)
def anexar(medicao_id: ID, arquivo: UploadFile = File(...), tipo_doc: str = Form("nfs"),
           usuario: dict = Depends(exigir("editar_cadastros")), conn: sqlite3.Connection = Depends(conexao)):
    """Arrasta a nota (ou a FRC): o PDF e' lido em subprocesso com limite de tempo; PDF hostil vira 415."""
    _medicao_existe(conn, medicao_id)
    pdf = _bytes_validados(arquivo)
    try:
        return notas.anexar_pdf(conn, usuario, medicao_id, pdf, arquivo.filename or "nota.pdf", tipo_doc)
    except leitura_pdf.TextoInadequado as e:
        raise HTTPException(415, str(e)) from e
    except ValueError as e:
        raise _erro_do_cliente(conn, e)


@router.post("/api/medicoes/{medicao_id}/notas/manual")
def manual(medicao_id: ID, dados: ManualIn, usuario: dict = Depends(exigir("editar_cadastros")),
           conn: sqlite3.Connection = Depends(conexao)):
    _medicao_existe(conn, medicao_id)
    try:
        valor = dinheiro.parse_brl(dados.valor)
        return notas.registrar_manual(conn, usuario, medicao_id, dados.documento_id, dados.numero,
                                      dados.emissao.isoformat(), valor)
    except ValueError as e:
        raise _erro_do_cliente(conn, e)


@router.post("/api/medicoes/{medicao_id}/notas/completa")
def completa(medicao_id: ID, dados: JustificativaIn, usuario: dict = Depends(exigir("editar_cadastros")),
             conn: sqlite3.Connection = Depends(conexao)):
    _medicao_existe(conn, medicao_id)
    try:
        notas.declarar_completa(conn, usuario, medicao_id, dados.justificativa)
    except ValueError as e:
        raise _erro_do_cliente(conn, e)
    return {"ok": True, "estado": medicoes.detalhe(conn, medicao_id)["estado"]}


class FrcIn(BaseModel):
    numero: int = Field(ge=1, le=99_999)


@router.get("/api/medicoes/{medicao_id}/frc")
def frc_situacao(medicao_id: ID, _=Depends(exigir("ver_paineis", com_csrf=False)),
                 conn: sqlite3.Connection = Depends(conexao)):
    """FRC da medicao de consorcio: notas esperadas (anexada ou falta), numero sugerido e a FRC gerada."""
    _medicao_existe(conn, medicao_id)
    return frc.situacao(conn, medicao_id)


@router.post("/api/medicoes/{medicao_id}/frc")
def frc_gerar(medicao_id: ID, dados: FrcIn, usuario: dict = Depends(exigir("editar_cadastros")),
              conn: sqlite3.Connection = Depends(conexao)):
    _medicao_existe(conn, medicao_id)
    try:
        frc.gerar(conn, usuario, medicao_id, dados.numero)
    except ValueError as e:
        raise _erro_do_cliente(conn, e)
    return frc.situacao(conn, medicao_id)


@router.get("/api/medicoes/{medicao_id}/frc/{formato}")
def frc_baixar(medicao_id: ID, formato: str, _=Depends(exigir("ver_paineis", com_csrf=False)),
               conn: sqlite3.Connection = Depends(conexao)):
    if formato not in ("pdf", "xlsx"):
        raise HTTPException(404, "Arquivo não encontrado")
    _medicao_existe(conn, medicao_id)
    try:
        caminho = frc.arquivo(conn, medicao_id, formato)
    except ValueError:
        caminho = None
    if caminho is None:
        raise HTTPException(404, "FRC ainda não gerada")
    tipo = arquivos.MIME if formato == "pdf" else arquivos.MIME_XLSX
    return FileResponse(caminho, media_type=tipo, filename=frc.nome_arquivo(conn, medicao_id, formato),
                        headers={"X-Content-Type-Options": "nosniff"})


@router.post("/api/notas/{nota_id}/justificar")
def justificar(nota_id: ID, dados: JustificativaIn, usuario: dict = Depends(exigir("editar_cadastros")),
               conn: sqlite3.Connection = Depends(conexao)):
    if not 1 <= nota_id <= MAX_INT64:
        raise HTTPException(404, "Nota não encontrada")
    try:
        notas.justificar(conn, usuario, nota_id, dados.justificativa)
    except ValueError as e:
        raise _erro_do_cliente(conn, e)
    return {"ok": True}
