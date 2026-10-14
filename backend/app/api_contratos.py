"""Leitura de contratos. Bloco 9: a escrita saiu; contrato entra pelo cadastro versionado."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app import contratos, diretoria, notas, prazos, tempo
from app.api_auth import conexao
from app.api_medicoes import ID
from app.permissoes import exigir

router = APIRouter(prefix="/api/contratos")


def _existe(conn: sqlite3.Connection, contrato_id: int) -> None:
    """404 antes de tocar no repositorio.

    As leituras de `contratos` assumem que o contrato existe (subscrito no fetchone)
    e estourariam TypeError com id inexistente -- a rota tem que barrar antes.
    """
    if conn.execute("SELECT id FROM contratos WHERE id=?", (contrato_id,)).fetchone() is None:
        raise HTTPException(404, "Contrato não encontrado")


@router.get("")
def listar(usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
           conn: sqlite3.Connection = Depends(conexao)):
    # A9: os dias ate' o fim da execucao e da vigencia e o pedido de prorrogacao em curso, por obra.
    hoje = tempo.hoje_local()
    return [{**c, **prazos.resumo(conn, c["id"], hoje)} for c in contratos.listar(conn)]


@router.get("/{contrato_id}")
def detalhe(contrato_id: ID, usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
            conn: sqlite3.Connection = Depends(conexao)):
    _existe(conn, contrato_id)
    return contratos.vigente(conn, contrato_id)


@router.get("/{contrato_id}/cabecalho")
def cabecalho(contrato_id: ID, _=Depends(exigir("ver_paineis", com_csrf=False)),
              conn: sqlite3.Connection = Depends(conexao)):
    _existe(conn, contrato_id)
    # A3: faturado e a receber da obra, em valor cheio, ao lado do valor vigente.
    return {**contratos.cabecalho(conn, contrato_id), **diretoria.da_obra(conn, contrato_id)}


@router.get("/{contrato_id}/cadastro")
def cadastro(contrato_id: ID, _=Depends(exigir("ver_paineis", com_csrf=False)),
             conn: sqlite3.Connection = Depends(conexao)):
    _existe(conn, contrato_id)
    return contratos.cadastro_da_obra(conn, contrato_id)


@router.get("/{contrato_id}/notas")
def notas_da_obra(contrato_id: ID, _=Depends(exigir("ver_paineis", com_csrf=False)),
                  conn: sqlite3.Connection = Depends(conexao)):
    _existe(conn, contrato_id)
    return notas.do_contrato(conn, contrato_id)
