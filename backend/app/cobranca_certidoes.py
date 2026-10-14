"""Cobranca de certidao por e-mail (plano 2026-10-09; decisao do Leonardo de 08/10/2026).

Vencidas: a cada 2 h entre 08:00 e 18:00 (Cuiaba). Vencendo em ate' 15 dias: uma vez por dia, na primeira
rodada a partir das 08:00. So' para o Leonardo, enviado da conta dele (`correio.enviar_e_registrar`). A mesma
lista nao sai duas vezes no mesmo intervalo (`cobranca_certidoes_envios`). Sem conta Microsoft conectada, so'
registra no log.

Destinatario e logins de quem envia vem do cadastro (geral.yaml, `cobranca_certidoes`, issue #110); sem eles,
so' registra no log.
"""
import datetime
import json
import logging
import threading
import time
from html import escape

from app import correio, db, documentos, entidades, graph, tempo

log = logging.getLogger("app.cobranca_certidoes")

INICIO, FIM = 8, 18
DIAS_VENCENDO = 15
INTERVALO_SEG = 600


def listas(conn, hoje: datetime.date) -> tuple[list[dict], list[dict]]:
    """(vencidas, vencendo em ate' 15 dias) das certidoes exigidas pelos contratos ativos."""
    cert, _, _, _ = documentos._exigidos_ativos(conn)
    vencidas, vencendo = [], []
    for eid in sorted(cert):
        e = entidades.detalhe(conn, eid)
        if e is None or not e["ativo"]:
            continue
        for t in sorted(cert[eid].values(), key=lambda t: t["id"]):
            s = documentos.situacao(conn, eid, t, hoje)
            linha = {"entidade_id": eid, "entidade": e.get("nome_curto") or e["nome"], "tipo_id": t["id"],
                     "tipo": t["nome"], "validade": (s["certidao"] or {}).get("validade"),
                     "link": t.get("link_emissao"), "dias": s["dias"]}
            if s["situacao"] == "vencida":
                vencidas.append(linha)
            elif s["situacao"] in ("ok", "vencendo") and s["dias"] <= DIAS_VENCENDO:
                vencendo.append(linha)
    return vencidas, vencendo


def _corpo(titulo: str, itens: list[dict]) -> str:
    linhas = [titulo, ""]
    for x in itens:
        validade = datetime.date.fromisoformat(x["validade"]).strftime("%d/%m/%Y") if x["validade"] else "—"
        linhas.append(f"- {x['entidade']} — {x['tipo']} — validade {validade}"
                      + (f" — emitir em: {x['link']}" if x["link"] else ""))
    return "".join(f"<p>{escape(l)}</p>" if l else "<p>&nbsp;</p>" for l in linhas)


def _ja_enviado(conn, motivo: str, itens: list[dict]) -> bool:
    feitos = {(r[0], r[1]) for r in conn.execute(
        "SELECT certidao_tipo, entidade_id FROM cobranca_certidoes_envios WHERE motivo=?", (motivo,))}
    return {(x["tipo_id"], x["entidade_id"]) for x in itens} <= feitos


def _config(conn) -> dict | None:
    r = conn.execute("SELECT valor FROM cadastro_geral WHERE chave='cobranca_certidoes'").fetchone()
    return json.loads(r["valor"]) if r else None


def _usuario(conn, logins: list[str]) -> dict | None:
    marcas = ",".join("?" * len(logins))
    r = conn.execute(f"SELECT id, email FROM usuarios WHERE ativo=1 AND lower(email) IN ({marcas}) ORDER BY id LIMIT 1",
                     logins).fetchone()
    return {"id": r["id"], "email": r["email"]} if r else None


def _enviar(conn, motivo: str, assunto: str, corpo: str, itens: list[dict]) -> bool:
    config = _config(conn)
    if config is None:
        log.warning("cobranca de certidoes sem destinatario no cadastro (geral.yaml): %s", assunto)
        return False
    usuario = _usuario(conn, config["enviada_por"])
    if usuario is None:
        log.warning("cobranca de certidoes sem usuario do Leonardo no cadastro: %s", assunto)
        return False
    try:
        correio.enviar_e_registrar(conn, usuario, "cobranca_certidoes", config["para"], [], assunto, corpo, [])
    except (graph.ErroGraph, RuntimeError) as e:
        log.warning("cobranca de certidoes nao enviada (%s): %s", assunto, e)
        return False
    with db.mutacao(conn):
        conn.executemany("INSERT INTO cobranca_certidoes_envios (certidao_tipo, entidade_id, motivo) VALUES (?,?,?)",
                         [(x["tipo_id"], x["entidade_id"], motivo) for x in itens])
    return True


def rodada(conn, agora_local: datetime.datetime) -> list[str]:
    """Uma passada do job; devolve os assuntos enviados."""
    # 08:00 a 18:00: a rodada das 18h vale so' nos primeiros minutos (o laco roda a cada 10 min).
    if not (INICIO <= agora_local.hour < FIM or (agora_local.hour == FIM and agora_local.minute < 10)):
        return []
    hoje = agora_local.date()
    vencidas, vencendo = listas(conn, hoje)
    enviados = []
    faixa = INICIO + (agora_local.hour - INICIO) // 2 * 2           # 08, 10, ..., 18
    motivo = f"vencidas {hoje.isoformat()} {faixa:02d}h"
    if vencidas and not _ja_enviado(conn, motivo, vencidas):
        assunto = f"Certidões vencidas ({len(vencidas)})"
        if _enviar(conn, motivo, assunto, _corpo("Certidões vencidas exigidas pelas obras ativas:", vencidas),
                   vencidas):
            enviados.append(assunto)
    motivo = f"vencendo {hoje.isoformat()}"
    ja_hoje = conn.execute("SELECT 1 FROM cobranca_certidoes_envios WHERE motivo=?", (motivo,)).fetchone()
    if vencendo and not ja_hoje:                                    # uma vez por dia
        assunto = f"Certidões vencendo em {DIAS_VENCENDO} dias ({len(vencendo)})"
        if _enviar(conn, motivo, assunto, _corpo(f"Certidões que vencem nos próximos {DIAS_VENCENDO} dias:",
                                                 vencendo), vencendo):
            enviados.append(assunto)
    return enviados


def agendar(intervalo_seg: int = INTERVALO_SEG) -> threading.Thread:
    def loop():
        while True:
            try:
                conn = db.get_conn()
                try:
                    rodada(conn, tempo.para_local(tempo.agora_utc()))
                finally:
                    conn.close()
            except Exception:
                log.exception("rodada da cobranca de certidoes falhou")
            time.sleep(intervalo_seg)

    t = threading.Thread(target=loop, name="cobranca-certidoes", daemon=True)
    t.start()
    return t
