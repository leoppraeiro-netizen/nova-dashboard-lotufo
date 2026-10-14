"""Conta Microsoft de cada usuario: conectar, ver o estado e mandar um e-mail de teste."""
import sqlite3
import threading
import time

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app import correio, graph
from app.api_auth import conexao
from app.permissoes import exigir

router = APIRouter(prefix="/api/correio")

# Estado do login por codigo de dispositivo, POR USUARIO, em memoria do processo (reiniciar o
# servidor no meio cancela o login; a pessoa pede outro codigo).
_LOGINS: dict[int, dict] = {}
_LOCK = threading.Lock()
_NENHUM = {"estado": "nenhum", "user_code": None, "verification_uri": None}


def _status(usuario_id: int) -> dict:
    cfg = correio.configuracao()
    with _LOCK:
        login = dict(_LOGINS.get(usuario_id, _NENHUM))
    return {"configurado": bool(cfg["client_id"] and cfg["tokens_dir"]) or bool(cfg["simulador"]),
            "conectado": correio.conectado(usuario_id), "login": login,
            "assinatura": correio.assinatura(usuario_id) is not None}


@router.get("/status")
def status(usuario: dict = Depends(exigir("ver_paineis", com_csrf=False))):
    # B-09 (10/10/2026): a diretoria abre /conta (e-mail e senha); so' ler o estado, as acoes seguem editar_cadastros
    return _status(usuario["id"])


def _acompanhar(usuario_id: int, cfg: dict, device_code: str, intervalo: int, expira: float) -> None:
    while time.time() < expira:
        time.sleep(intervalo)
        try:
            r = graph.concluir_device_code(cfg["tenant"], cfg["client_id"], device_code,
                                           correio.arquivo_token(usuario_id))
        except graph.ErroGraph as e:
            with _LOCK:
                _LOGINS[usuario_id] = {"estado": "erro", "erro": str(e), "user_code": None,
                                       "verification_uri": None}
            return
        if r != "pendente":
            with _LOCK:
                _LOGINS[usuario_id] = {"estado": r, "user_code": None, "verification_uri": None}
            return
    with _LOCK:
        _LOGINS[usuario_id] = {"estado": "expirado", "user_code": None, "verification_uri": None}


@router.post("/conectar")
def conectar(usuario: dict = Depends(exigir("editar_cadastros"))):
    cfg = correio.configuracao()
    if not (cfg["client_id"] and cfg["tokens_dir"]):
        raise HTTPException(422, "Microsoft 365 não configurado neste servidor "
                                 "(DASH_GRAPH_CLIENT_ID / DASH_GRAPH_TOKENS_DIR) — ver docs/runbook.md")
    uid = usuario["id"]
    with _LOCK:
        if _LOGINS.get(uid, {}).get("estado") == "aguardando":
            return _status(uid)
    try:
        d = graph.iniciar_device_code(cfg["tenant"], cfg["client_id"], correio.ESCOPOS_LOGIN)
    except graph.ErroGraph as e:
        raise HTTPException(502, str(e)) from None
    with _LOCK:
        _LOGINS[uid] = {"estado": "aguardando", "user_code": d["user_code"],
                        "verification_uri": d["verification_uri"]}
    threading.Thread(target=_acompanhar, daemon=True,
                     args=(uid, cfg, d["device_code"], d["interval"], time.time() + d["expires_in"])).start()
    return _status(uid)


@router.post("/teste")
def teste(usuario: dict = Depends(exigir("editar_cadastros")),
          conn: sqlite3.Connection = Depends(conexao)):
    c_usuario = {"id": usuario["id"], "email": usuario["email"]}
    try:
        destino = correio.cliente(usuario["id"], usuario["email"]).remetente()
        eid = correio.enviar_e_registrar(
            conn, c_usuario, "teste", [destino], [], "Dashboard Lotufo — teste de envio",
            "<p>Este e-mail confirma que a Dashboard Lotufo consegue enviar pela sua conta.</p>",
            [("teste.txt", "Anexo de teste da Dashboard Lotufo.\n".encode("utf-8"))])
    except graph.ErroGraph as e:
        raise HTTPException(422, str(e)) from None
    return {"envio_id": eid, "remetente": destino}


@router.get("/remetente")
def remetente(usuario: dict = Depends(exigir("editar_cadastros", com_csrf=False))):
    """A conta que aparece em "De:" no envio (a conta Microsoft conectada)."""
    try:
        return {"remetente": correio.cliente(usuario["id"], usuario["email"]).remetente(), "erro": None}
    except graph.ErroGraph as e:
        return {"remetente": None, "erro": str(e)}


@router.get("/contatos")
def contatos(q: str = Query(default="", max_length=100), todos: bool = False,
             usuario: dict = Depends(exigir("editar_cadastros", com_csrf=False)),
             conn: sqlite3.Connection = Depends(conexao)):
    return correio.contatos(conn, usuario["id"], q, todos)


@router.get("/assinatura")
def ver_assinatura(usuario: dict = Depends(exigir("editar_cadastros", com_csrf=False))):
    a = correio.assinatura(usuario["id"])
    if a is None:
        raise HTTPException(404, "Sem assinatura cadastrada")
    return Response(a[0], media_type=a[1], headers={"Cache-Control": "no-store"})


@router.post("/assinatura")
def gravar_assinatura(arquivo: UploadFile = File(...), usuario: dict = Depends(exigir("editar_cadastros")),
                      conn: sqlite3.Connection = Depends(conexao)):
    dados = arquivo.file.read(correio.ASSINATURA_MAX + 1)
    try:
        correio.gravar_assinatura(conn, usuario["id"], dados)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return _status(usuario["id"])


@router.delete("/assinatura")
def remover_assinatura(usuario: dict = Depends(exigir("editar_cadastros")),
                       conn: sqlite3.Connection = Depends(conexao)):
    correio.remover_assinatura(conn, usuario["id"])
    return _status(usuario["id"])

