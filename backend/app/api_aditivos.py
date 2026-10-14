"""Leitura de aditivos: lista do contrato e conferencia do aditivo.

Bloco 9: a escrita (rascunho, assinatura, cancelamento, leitura do termo em PDF) saiu; aditivo entra
pelo cadastro versionado (`cadastro/*.yaml` + `python -m app.cli cadastro aplicar`)."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app import aditivos
from app.api_auth import conexao
from app.api_medicoes import ID
from app.permissoes import exigir

router = APIRouter()

MAX_INT64 = 9223372036854775807


def _contrato_existe(conn, contrato_id: int) -> None:
    if conn.execute("SELECT 1 FROM contratos WHERE id=?", (contrato_id,)).fetchone() is None:
        raise HTTPException(404, "Contrato não encontrado")


def _aditivo_existe(conn, aditivo_id: int) -> None:
    if not 1 <= aditivo_id <= MAX_INT64 or aditivos.detalhe(conn, aditivo_id) is None:
        raise HTTPException(404, "Aditivo não encontrado")


@router.get("/api/contratos/{contrato_id}/aditivos")
def listar(contrato_id: ID, usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
           conn: sqlite3.Connection = Depends(conexao)):
    _contrato_existe(conn, contrato_id)
    return aditivos.listar(conn, contrato_id)


@router.get("/api/aditivos/{aditivo_id}/conferencia")
def conferencia(aditivo_id: ID, usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
                conn: sqlite3.Connection = Depends(conexao)):
    _aditivo_existe(conn, aditivo_id)
    return aditivos.conferencia(conn, aditivo_id)
