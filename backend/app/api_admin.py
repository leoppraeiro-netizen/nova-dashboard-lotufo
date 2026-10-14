import datetime
import sqlite3
from fastapi import APIRouter, Depends, Query
from app import auditoria, backup, correio, tempo
from app.api_auth import conexao
from app.permissoes import exigir

router = APIRouter(prefix="/api/admin")
MAX_INT64 = 9223372036854775807

@router.get("/auditoria")
def listar_auditoria(limite: int = Query(default=100, ge=1, le=500),
                     antes_de: int | None = Query(default=None, ge=1, le=MAX_INT64),
                     usuario: dict = Depends(exigir("administrar", com_csrf=False)),
                     conn: sqlite3.Connection = Depends(conexao)):
    """Do mais recente ao mais antigo. `antes_de` e' o cursor: o id do ultimo evento da pagina anterior.
    A cadeia e' verificada so' na primeira pagina (sem cursor); nas seguintes `cadeia_integra` vem nulo."""
    # um a mais que o pedido so' para saber se ainda ha' anteriores
    linhas = conn.execute(
        "SELECT * FROM audit_log WHERE id < ? ORDER BY id DESC LIMIT ?",
        (MAX_INT64 if antes_de is None else antes_de, limite + 1)).fetchall()
    return {"cadeia_integra": auditoria.verificar_cadeia(conn) if antes_de is None else None,
            "ha_mais": len(linhas) > limite,
            "eventos": [dict(l) for l in linhas[:limite]]}


@router.get("/backup")
def saude_do_backup(usuario: dict = Depends(exigir("administrar", com_csrf=False))):
    """Administracao > Saude (issue #31): ultimo backup, quantos estao guardados, ultimo erro
    e se esta atrasado (mais de 2 h sem snapshot). So' admin: traz caminhos e erros do servidor."""
    return backup.situacao(backup.pasta_local(), backup.pasta_externa() is not None, tempo.agora_utc())


@router.get("/contas-microsoft")
def contas_microsoft(usuario: dict = Depends(exigir("administrar", com_csrf=False)),
                     conn: sqlite3.Connection = Depends(conexao)):
    """Quem tem a conta Microsoft conectada (bloco 9). Cada pessoa conecta a propria em Minha conta;
    aqui so' se ve. `token_em` = quando o arquivo do token foi gravado pela ultima vez."""
    contas = []
    for u in conn.execute("SELECT id, nome, email, perfil FROM usuarios WHERE ativo=1 ORDER BY nome"):
        token_em = None
        if correio.conectado(u["id"]):
            mtime = correio.arquivo_token(u["id"]).stat().st_mtime
            token_em = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).isoformat(timespec="seconds")
        contas.append({"usuario_id": u["id"], "nome": u["nome"], "email": u["email"], "perfil": u["perfil"],
                       "conectada": token_em is not None, "token_em": token_em})
    return contas
