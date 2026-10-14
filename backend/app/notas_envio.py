"""Notas a enviar ao contratante (plano 2026-10-09; mapeamento 2026-10-08 §3, §5, §6a).

Nota emitida -> envio da nota ao orgao (pelo sistema, sobre `protocolo` etapa `nota`/`unico`, ou registrado
como feito por fora) -> aguardando pagamento (= `protocolada`). Um ENVIO e' um e-mail: na SINFRA e na Pref. VG
medicao e reajuste da mesma competencia vao juntos (D9); na MTPAR e na SES, um por medicao.
"""
import datetime
import json
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime

from app import arquivos, auditoria, certidoes, db, documentos, frc, medicoes, oficios, protocolo, tempo

SUB_SINFRA = {"sinfra-sagpm": "SAGPM", "sinfra-suef1": "SUEF I", "sinfra-suef2": "SUEF II", "sinfra-supu": "SUPU",
              "sinfra-sacid": "SACID"}
AVISO_DIAS = 15                    # D8: certidao a menos de 15 dias = aviso
NATUREZA = {"execucao": "medição", "reajuste": "reajuste", "projeto": "projeto"}
TETO_EML = 25 * 1024 * 1024
# A-11 (testes de quebra 10/10/2026): um PNG renomeado para .eml virou evidencia e protocolou. Sinais de que nao e' e-mail.
BINARIOS = (b"%PDF-", b"\x89PNG", b"PK\x03\x04", b"\xff\xd8\xff")
NAO_E_EML = ("O arquivo não é um e-mail salvo (.eml): na caixa de Enviados do Outlook, arraste o e-mail para uma "
             "pasta do computador e anexe o arquivo .eml gerado")
_PIOR = {"ok": 0, "aviso": 1, "falta": 2, "vencida": 3}


def _grupo(familia: str, o: dict) -> str:
    return {"sinfra": "SINFRA", "mtpar": "MTPAR", "ses": "SES-MT"}.get(familia) or \
        {"pref-vg": "Pref. VG", "pref-cuiaba": "Pref. Cuiabá"}.get(o["chave"], o["nome"])


def _etapa(familia: str) -> str:
    return "nota" if familia == "sinfra" else "unico"


def _br(iso: str, fmt: str = "%d/%m/%Y") -> str:
    return datetime.date.fromisoformat(iso[:10]).strftime(fmt)


def _ativos(conn, etapa: str, medicao_id: int) -> list[dict]:
    """Protocolos de envio da nota ainda nao enviados nem descartados que contem a medicao."""
    return [dict(r) for r in conn.execute(
        "SELECT p.* FROM protocolo_medicoes pm JOIN protocolos p ON p.id=pm.protocolo_id WHERE pm.medicao_id=? "
        "AND p.etapa=? AND p.situacao NOT IN ('descartado','enviado') ORDER BY p.id DESC", (medicao_id, etapa))]


def _descricao(ms: list[dict]) -> str:
    if len(ms) == 2 and {m["tipo"] for m in ms} == {"execucao", "reajuste"} and len({m["numero"] for m in ms}) == 1:
        return f"{ms[0]['numero']}ª medição + reajuste"
    return " + ".join(medicoes.titulo(m).replace("Medição", "medição") for m in ms)


# --- itens do envio --------------------------------------------------------------------------------

def _itens(conn, c: dict, familia: str, ms: list[dict], hoje: datetime.date) -> tuple[list[dict], list[dict], list[str]]:
    """(itens, notas, avisos curtos). Estados: ok | aviso (<15 dias) | falta (justifica) | vencida (bloqueia)."""
    e = protocolo._etapa(familia, _etapa(familia))
    ids = [m["id"] for m in ms]
    docs = [dict(r) for r in conn.execute(
        f"SELECT id, medicao_id, tipo_doc, nome, numero_nf, municipio, consorciada FROM medicao_documentos "
        f"WHERE medicao_id IN ({','.join('?' * len(ids))}) AND tipo_doc IN ('nfs','nf','fatura') "
        f"AND arquivo IS NOT NULL ORDER BY tipo_doc='fatura', id", ids)]
    tipo_de = {m["id"]: m["tipo"] for m in ms}
    nfs = [d for d in docs if d["tipo_doc"] != "fatura"]
    notas = [{"numero": d["numero_nf"], "natureza": tipo_de[d["medicao_id"]], "municipio": d["municipio"],
              "arquivo": d["nome"], "consorciada": d["consorciada"], "medicao_id": d["medicao_id"],
              "valor_centavos": None} for d in nfs]
    itens, curtos = [], []
    sem_nota = [m for m in ms if not any(d["medicao_id"] == m["id"] for d in nfs)]
    por_natureza = {}
    for d in nfs:
        por_natureza.setdefault(NATUREZA[tipo_de[d["medicao_id"]]], []).append(d["numero_nf"] or d["nome"])
    detalhe = " · ".join(f"NFS {', '.join(v)} ({k})" for k, v in por_natureza.items())
    if sem_nota:
        detalhe = "; ".join(x for x in (detalhe, "Falta a nota: " + ", ".join(medicoes.titulo(m) for m in sem_nota))
                            if x)
        curtos.append("Falta a nota fiscal")
    itens.append({"chave": "notas", "rotulo": f"Notas fiscais ({len(nfs)})" if len(nfs) != 1 else "Nota fiscal (1)",
                  "detalhe": detalhe, "estado": "falta" if sem_nota else "ok"})
    if c.get("entidade_id"):
        faltas = protocolo.faltas_consorcio(conn, c, ms)
        consorciadas = conn.execute("SELECT 1 FROM entidade_consorciadas WHERE consorcio_id=?",
                                    (c["entidade_id"],)).fetchone()
        if consorciadas:
            # FRC (2026-10-09): a dashboard gera a FRC sem assinatura na etapa 3; o que vai ao orgao e' a ASSINADA,
            # anexada aqui como documento `fatura` (uma por medicao). Arrastar e soltar no proprio item.
            frcs = {d["medicao_id"]: d for d in docs if d["tipo_doc"] == "fatura"}
            for m in ms:
                d = frcs.get(m["id"])
                # issue #148: a FRC gerada (sem assinatura) vigente, para a etapa 4 oferecer baixa-la; desatualizada
                # (as notas mudaram depois dela) nao se oferece: assinaria valores velhos
                g = None if d else frc.situacao(conn, m["id"]).get("frc")
                detalhe = (f"Assinada anexada · {d['nome']}" if d
                           else "Falta a assinada: as notas mudaram depois da FRC gerada; gere de novo na etapa 3 "
                                "(Nota fiscal), assine no DocuSign e anexe aqui" if g and g["desatualizada"]
                           else "Falta a assinada: baixe a FRC gerada, assine no DocuSign e anexe aqui" if g
                           else "Falta a FRC assinada: gere na etapa 3 (Nota fiscal), assine no DocuSign e anexe aqui")
                itens.append({"chave": f"frc:{m['id']}", "medicao_id": m["id"],
                              "rotulo": "FRC assinada" + (f" · {medicoes.titulo(m)}" if len(ms) > 1 else ""),
                              "detalhe": detalhe, "frc_gerada": g["numero"] if g and not g["desatualizada"] else None,
                              "estado": "ok" if d else "falta", "acao": None if d else "anexar_frc"})
            notas_faltam = [f for f in faltas if not f.endswith("FRC assinada não anexada")]
            itens.append({"chave": "consorcio", "rotulo": "Notas das consorciadas",
                          "detalhe": "; ".join(notas_faltam) or "todas anexadas",
                          "estado": "falta" if notas_faltam else "ok"})
            curtos += faltas
    natureza = "execucao" if any(m["tipo"] != "reajuste" for m in ms) else "reajuste"
    ex = documentos.exigidos(conn, c["id"], natureza)
    varias = len(ex["entidades"]) > 1
    for eid in ex["entidades"] if ex["tipos"] else []:
        ent = dict(conn.execute("SELECT * FROM entidades WHERE id=?", (eid,)).fetchone())
        nome = ent["nome_curto"] or ent["nome"]
        estado, msgs = "ok", []
        for t in ex["tipos"]:
            s = documentos.situacao(conn, eid, t, hoje)
            rot = documentos.ROTULO.get(t["chave"], t["nome"])
            if s["situacao"] == "vencida":
                est, msg = "vencida", f"{rot} vencida em {_br(s['certidao']['validade'], '%d/%m')}"
            elif s["situacao"] == "faltando":
                est, msg = "falta", f"{rot} sem certidão"
            elif s["situacao"] in ("ok", "vencendo") and s["dias"] < AVISO_DIAS:
                est, msg = "aviso", f"{rot} vence hoje" if s["dias"] == 0 else \
                    f"{rot} vence em {s['dias']} dia{'s' if s['dias'] > 1 else ''}"
            else:
                continue
            msgs.append(msg)
            estado = max(estado, est, key=_PIOR.get)
        item = {"chave": f"certidoes:{ent['chave'] or eid}", "rotulo": f"Certidões {nome} ({len(ex['tipos'])})",
                "detalhe": " · ".join(msgs) or "todas válidas", "estado": estado, "entidade_id": eid}
        if estado in ("vencida", "falta"):
            item["acao"] = "anexar_certidao"
        itens.append(item)
        curtos += [f"{nome}: {x}" if varias else x for x in msgs]
    if ex["regularidade"] and "regularidade" in e.soltos:
        eid = ex["regularidade"]
        ent = dict(conn.execute("SELECT * FROM entidades WHERE id=?", (eid,)).fetchone())
        s = documentos.situacao_regularidade(conn, eid, hoje)
        mes = f"{s['esperada'][5:7]}/{s['esperada'][:4]}"
        item = {"chave": f"regularidade:{ent['chave'] or eid}", "rotulo": "Regularidade mensal",
                "entidade_id": eid, "competencia": s["esperada"]}
        if s["situacao"] == "ok":
            item.update(detalhe=f"{s['competencia'][5:7]}/{s['competencia'][:4]}", estado="ok")
        else:
            item.update(detalhe=f"O DP ainda não enviou o arquivo de {mes}", estado="falta",
                        acao="anexar_regularidade")
            curtos.append("Falta a regularidade")
        itens.append(item)
    return itens, notas, curtos


def _irmas(conn, c: dict, familia: str, o: dict, ms: list[dict], hoje: datetime.date) -> list[dict]:
    """Issue #172: onde medicao e reajuste vao no mesmo e-mail (SINFRA, Pref. VG), a irma (mesmo numero, o outro tipo
    do par execucao x reajuste) com nota emitida que ficou fora deste envio, para o registro por fora leva-la junto.
    Nao se oferece a irma bloqueada (certidao vencida da natureza dela: o registro por fora contornaria o bloqueio)
    nem a que tem envio proprio ja' montado ou assinado (o registro descartaria esse protocolo); rascunho nao conta."""
    regras = json.loads(o.get("regras") or "{}")
    if not protocolo.junta_naturezas(regras, o, protocolo._etapa(familia, _etapa(familia))):
        return []
    dentro = {m["id"] for m in ms}
    outro = {"execucao": "reajuste", "reajuste": "execucao"}
    achadas: dict[int, dict] = {}
    for m in ms:
        if m["tipo"] not in outro:
            continue
        for r in conn.execute("SELECT * FROM medicoes WHERE contrato_id=? AND numero=? AND tipo=? "
                              "AND estado='nota_emitida' ORDER BY id", (c["id"], m["numero"], outro[m["tipo"]])):
            if r["id"] in dentro or any(p["situacao"] != "rascunho" for p in _ativos(conn, _etapa(familia), r["id"])):
                continue
            if any(i["estado"] == "vencida" for i in _itens(conn, c, familia, [dict(r)], hoje)[0]):
                continue
            achadas[r["id"]] = {"medicao_id": r["id"], "titulo": medicoes.titulo(r), "tipo": r["tipo"]}
    return list(achadas.values())


def _envio(conn, c: dict, familia: str, o: dict, ms: list[dict], protocolo_id: int | None,
           hoje: datetime.date) -> dict:
    itens, notas, curtos = _itens(conn, c, familia, ms, hoje)
    estados = {i["estado"] for i in itens}
    situacao = "bloqueado" if "vencida" in estados else "pendente" if "falta" in estados else \
        "a_pedido" if o["chave"] == "pref-cuiaba" else "pronto"
    ids = sorted(m["id"] for m in ms)
    emitida = max((m["desde"] for m in ms if m.get("desde")), default=None)
    return {"chave": f"c{c['id']}:" + "-".join(f"m{i}" for i in ids), "contrato_id": c["id"],
            "obra": c.get("nome_curto") or c.get("numero_instrumento"), "orgao": _grupo(familia, o),
            "orgao_sub": SUB_SINFRA.get(o["chave"]) if familia == "sinfra" else None, "familia": familia,
            "grupo": _grupo(familia, o), "a_pedido": o["chave"] == "pref-cuiaba", "medicao_ids": ids,
            "descricao": _descricao(ms), "notas": notas,
            "valor_centavos": sum(m.get("valor_centavos") or 0 for m in ms), "emitida_em": emitida,
            "dias": (hoje - datetime.date.fromisoformat(emitida)).days if emitida else None,
            "situacao": situacao, "aviso": " · ".join(dict.fromkeys(curtos)) or None, "itens": itens,
            "protocolo_id": protocolo_id, "irmas": _irmas(conn, c, familia, o, ms, hoje)}


# --- lista -----------------------------------------------------------------------------------------

def a_enviar(conn, hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    por_contrato: dict[int, list[dict]] = {}
    for m in medicoes.em_andamento(conn, estado="nota_emitida"):
        por_contrato.setdefault(m["contrato_id"], []).append(m)
    envios = []
    for cid, ms in por_contrato.items():
        c = protocolo._contrato(conn, cid)
        if not c.get("orgao_id"):
            continue                          # sem orgao no cadastro nao ha para quem mandar
        familia, regras, o = protocolo._orgao(conn, c)
        etapa = _etapa(familia)
        junta = protocolo.junta_naturezas(regras, o, protocolo._etapa(familia, etapa))
        grupos: dict[tuple, list[dict]] = {}
        for m in ms:                          # protocolo ja' iniciado manda; senao a regra do orgao
            ativos = _ativos(conn, etapa, m["id"])
            k = ("p", ativos[0]["id"]) if ativos else ("c", m["competencia"]) if junta else ("m", m["id"])
            grupos.setdefault(k, []).append(m)
        for k, gm in grupos.items():
            envios.append(_envio(conn, c, familia, o, gm, k[1] if k[0] == "p" else None, hoje))
    contadores = {"Todas": len(envios)}
    for x in envios:
        contadores[x["grupo"]] = contadores.get(x["grupo"], 0) + 1
    return {"envios": envios, "contadores": contadores}


# --- iniciar, detalhe, enviar ----------------------------------------------------------------------

def iniciar(conn, usuario_id: int, contrato_id: int, medicao_ids: list[int], numero_oficio: str | None = None) -> int:
    """Cria (ou devolve) o protocolo do envio. Outra composicao (juntar/separar) descarta o que nao foi enviado."""
    c = protocolo._contrato(conn, contrato_id)
    familia, regras, o = protocolo._orgao(conn, c)
    etapa = _etapa(familia)
    e = protocolo._etapa(familia, etapa)
    ids = sorted(set(medicao_ids or []))
    if not ids:
        raise ValueError("Escolha ao menos uma medição")
    for mid in ids:
        m = conn.execute("SELECT * FROM medicoes WHERE id=?", (mid,)).fetchone()
        if m is None or m["contrato_id"] != contrato_id:
            raise ValueError("Medição de outro contrato")
        if m["estado"] != "nota_emitida":
            raise ValueError(f"{medicoes.titulo(m)} não está com a nota emitida ({m['estado']})")
    if len(ids) > 1 and not protocolo.junta_naturezas(regras, o, e):
        raise ValueError("Neste órgão cada nota vai no seu e-mail (um ofício por nota)")
    ativos = {p["id"]: p for mid in ids for p in _ativos(conn, etapa, mid)}
    canon = None
    if e.carta and numero_oficio:
        sigla = conn.execute("SELECT sigla_oficio FROM entidades WHERE id=?",
                             (c["entidade_id"],)).fetchone()["sigla_oficio"] if c.get("entidade_id") else "LT"
        canon = oficios.canonico(numero_oficio, sigla, tempo.hoje_local().year)
    for p in ativos.values():
        atuais = sorted(r[0] for r in conn.execute("SELECT medicao_id FROM protocolo_medicoes WHERE protocolo_id=?",
                                                   (p["id"],)))
        if atuais == ids and (canon is None or canon == p["numero_oficio"]):
            return p["id"]
    anterior = next((p["numero_oficio"] for p in ativos.values() if p["numero_oficio"]), None)
    with db.mutacao(conn):
        for p in ativos.values():
            protocolo.descartar(conn, usuario_id, p["id"], "Envio recomposto na página Notas")
        return protocolo.criar(conn, usuario_id, contrato_id, etapa, ids, numero_oficio or anterior)


def _paginas(conn, p: dict, familia: str, regras: dict, hoje: datetime.date) -> list[str]:
    """O que vai dentro do PDF unico, na ordem de `montar` (MTPAR: oficio, NF, municipal, trabalhista...)."""
    e = protocolo._etapa(familia, p["etapa"])
    ms = protocolo._medicoes(conn, p["id"])
    out = ["Capa"] if e.capa else []
    for parte in e.partes:
        if parte == "carta":
            out.append(f"Ofício {oficios.na_carta(p['numero_oficio'])}" if p["numero_oficio"] else "Ofício")
        elif parte == "notas":
            out += [("FRC " if d["tipo_doc"] == "fatura" else "NF ") + (d["numero_nf"] or d["nome"])
                    for d in protocolo._docs_nota(conn, [m["id"] for m in ms])]
        elif parte == "certidoes":
            ex = documentos.exigidos(conn, p["contrato_id"], p["natureza"])
            ordem = regras.get("ordem_certidoes") or sorted(t["chave"] for t in ex["tipos"])
            tipos = sorted(ex["tipos"], key=lambda t: ordem.index(t["chave"]) if t["chave"] in ordem else 99)
            for eid in ex["entidades"]:
                ent = conn.execute("SELECT nome, nome_curto FROM entidades WHERE id=?", (eid,)).fetchone()
                for t in tipos:
                    v = certidoes.vigente(conn, eid, t["id"], hoje.isoformat())
                    if v and v.get("arquivo"):
                        out.append(f"Certidão {documentos.ROTULO.get(t['chave'], t['nome'])} – "
                                   f"{ent['nome_curto'] or ent['nome']}")
        elif parte == "pecas":
            out += [x["nome"] for x in protocolo._pecas(conn, p["id"]) if x["ext"] == "pdf" and x["tipo"] != protocolo.ANEXO]
    return out


def detalhe_envio(conn, protocolo_id: int, remetente: str | None = None, hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    p = protocolo._linha(conn, protocolo_id)
    if p["etapa"] not in ("nota", "unico"):
        raise ValueError("Este protocolo não é de envio de nota")
    c = protocolo._contrato(conn, p["contrato_id"])
    familia, regras, o = protocolo._orgao(conn, c)
    e = protocolo._etapa(familia, p["etapa"])
    mids = {m["id"] for m in protocolo._medicoes(conn, protocolo_id)}
    ms = [m for m in medicoes.em_andamento(conn, contrato_id=c["id"]) if m["id"] in mids]
    pv = protocolo.previa_envio(conn, [protocolo_id], remetente=remetente, hoje=hoje)
    carta = None
    if e.carta:
        try:
            corpo = p["corpo_carta"] or protocolo.corpo_padrao(conn, protocolo_id)
        except ValueError:
            corpo = None
        carta = {"oficio": oficios.na_carta(p["numero_oficio"]) if p["numero_oficio"] else None, "corpo": corpo,
                 "paginas": _paginas(conn, p, familia, regras, hoje), "montado": bool(p["montado_arquivo"]),
                 "assinado": bool(p["assinado_arquivo"]),
                 "nome_arquivo": protocolo.nome_arquivo(conn, p) if p["montado_arquivo"] else None}
    return {"envio": _envio(conn, c, familia, o, ms, protocolo_id, hoje) if ms else None, "familia": familia,
            "etapa": p["etapa"], "protocolo_id": protocolo_id, "situacao_protocolo": p["situacao"], "carta": carta,
            "previa": {k: pv[k] for k in ("para", "copia", "assunto", "corpo", "anexos", "total", "limite", "links")},
            "bloqueio": pv["bloqueio"], "pendencias": [x["mensagem"] for x in pv["pendencias"]],
            "justificativa_obrigatoria": bool(pv["pendencias"]),
            "extras": [{"id": x["id"], "nome": x["nome"], "tamanho": x["tamanho"]}
                       for x in protocolo._pecas(conn, protocolo_id) if x["tipo"] == protocolo.ANEXO]}


def enviar(conn, usuario: dict, protocolo_id: int, para: list[str], copia: list[str], assunto: str, corpo: str,
           justificativa: str | None, cco: list[str] | None = None, *, anexos_previa: list[dict]) -> int:
    """Envia pelo Outlook de quem esta' logado e marca `protocolada` (protocolo.enviar). Bloqueio -> protocolo.Bloqueio.
    `anexos_previa` (issue #100): os anexos que a tela mostrou; se o servidor montar outros, recusa antes de reservar
    (protocolo.AnexosMudaram). Obrigatorio (gate Sol S1, PR #141): None nao vira envio sem conferencia."""
    if anexos_previa is None:
        raise ValueError("Faltam os anexos da prévia: abra a prévia de novo para conferir o que vai no e-mail")
    p = protocolo._linha(conn, protocolo_id)
    if p["etapa"] not in ("nota", "unico"):
        raise ValueError("Este protocolo não é de envio de nota")
    return protocolo.enviar(conn, usuario, [protocolo_id], para, copia, assunto, corpo, justificativa, cco=cco,
                            anexos_previa=anexos_previa)


# --- envio feito por fora --------------------------------------------------------------------------

def _e_email(dados: bytes) -> bool:
    """E-mail salvo: nao comeca por assinatura de binario, From com endereco de verdade, Date interpretavel e To ou
    Subject preenchido (gate Sol S3, 10/10/2026: "From: x" e "Date: y" digitados num texto passavam). A data NAO e'
    comparada com a do envio informado: fuso e reencaminhamento tornariam isso fragil."""
    if dados.startswith(BINARIOS):
        return False
    try:
        cab = BytesParser(policy=policy.default).parsebytes(dados, headersonly=True)
        _, endereco = parseaddr(str(cab.get("From") or ""))
        usuario, _, dominio = endereco.rpartition("@")
        if not usuario or "." not in dominio:
            return False
        parsedate_to_datetime(str(cab.get("Date") or ""))
        return any(str(cab.get(k) or "").strip() for k in ("To", "Subject"))
    except Exception:       # cabecalho torto quebra o parser de varios jeitos: para nos e' "nao e' e-mail"
        return False


def _conferir_externo(conn, ids: list[int], irmas: set[int]) -> list[dict]:
    """As medicoes do registro por fora, conferidas. Roda antes de gravar o .eml e de novo DENTRO da transacao
    (revisor da PR #178): outro registro ou envio entre as duas leituras nao pode passar. Recusa a medicao fora de
    `nota_emitida`, contratos diferentes, protocolo com envio reservado (o e-mail esta' saindo pelo sistema) e, em
    `irmas` (as que a tela juntou a' medicao da pagina), a que `_irmas` nao ofereceria."""
    ms = []
    for mid in ids:
        m = conn.execute("SELECT * FROM medicoes WHERE id=?", (mid,)).fetchone()
        if m is None:
            raise ValueError(f"Medição {mid} não encontrada")
        if m["estado"] != "nota_emitida":
            raise ValueError(f"{medicoes.titulo(m)} não está com a nota emitida ({m['estado']})")
        ms.append(dict(m))
    if len({m["contrato_id"] for m in ms}) > 1:       # issue #172: um e-mail e' de um contrato so'
        raise ValueError("Medição de outro contrato")
    for m in ms:
        if any(p["envio_reservado_em"] for etapa in ("nota", "unico") for p in _ativos(conn, etapa, m["id"])):
            raise ValueError(f"{medicoes.titulo(m)} está sendo enviada pelo sistema agora: confira o envio dela "
                             "antes de registrar por fora")
    if irmas:
        c = protocolo._contrato(conn, ms[0]["contrato_id"])
        familia, _, o = protocolo._orgao(conn, c)
        principais = [m for m in ms if m["id"] not in irmas]
        validas = {i["medicao_id"] for i in _irmas(conn, c, familia, o, principais, tempo.hoje_local())}
        for m in ms:
            if m["id"] in irmas and m["id"] not in validas:
                raise ValueError(f"{medicoes.titulo(m)} não pode ir neste registro (envio próprio montado ou "
                                 "assinado, bloqueio ou órgão que tramita separado): registre-a no envio dela")
    return ms


def envio_externo(conn, usuario_id: int, medicao_ids: list[int], enviado_em: str, observacao: str,
                  eml: tuple[str, bytes] | None = None, irma_ids: list[int] | None = None) -> None:
    """`irma_ids` (issue #172): a irma marcada no formulario, alem das medicoes do envio (`medicao_ids`)."""
    irmas = set(irma_ids or []) - set(medicao_ids or [])
    ids = sorted(set(medicao_ids or []) | irmas)
    if not set(medicao_ids or []):
        raise ValueError("Escolha ao menos uma medição")
    try:
        data = datetime.date.fromisoformat(enviado_em)
    except (TypeError, ValueError):
        raise ValueError("Data do envio inválida (use AAAA-MM-DD)") from None
    if data > tempo.hoje_local():
        raise ValueError("A data do envio não pode ser futura")
    obs = (observacao or "").strip()
    if not obs:
        raise ValueError("Informe a observação (como e para quem a nota foi enviada)")
    _conferir_externo(conn, ids, irmas)
    rel = sha = None
    if eml:
        if len(eml[1]) > TETO_EML:
            raise ValueError("Arquivo .eml acima de 25 MB")
        if not _e_email(eml[1]):
            raise ValueError(NAO_E_EML)
        rel, sha = arquivos.gravar_bytes("evidencias", eml[1], "eml")
    with db.mutacao(conn):
        ms = _conferir_externo(conn, ids, irmas)        # de novo, sob o lock: a corrida perdida e' recusada
        for m in ms:
            medicoes.registrar_protocolo(conn, usuario_id, m["id"], data.isoformat(),
                                         protocolo._oficio_da_medicao(conn, m["id"]), None, "manual",
                                         apesar_das_pendencias=True, justificativa=f"Envio feito por fora: {obs}")
            conn.execute("UPDATE medicoes SET envio_origem='externo', envio_externo_em=?, envio_externo_obs=? "
                         "WHERE id=?", (data.isoformat(), obs, m["id"]))
            if rel:
                conn.execute("INSERT OR IGNORE INTO medicao_documentos (medicao_id, fonte, tipo_doc, nome, item_id, "
                             "arquivo, sha256, tamanho) VALUES (?,'operacao','evidencia_orgao',?,?,?,?,?)",
                             (m["id"], (eml[0] or "envio.eml")[-200:], sha, rel, sha, len(eml[1])))
            for etapa in ("nota", "unico"):
                for p in _ativos(conn, etapa, m["id"]):
                    protocolo.descartar(conn, usuario_id, p["id"], "Envio registrado como feito por fora")
        auditoria.registrar(conn, usuario_id, "notas.envio_externo", "medicao", ids[0], None,
                            {"medicoes": ids, "enviado_em": data.isoformat(), "observacao": obs, "eml": rel})


# --- aguardando pagamento --------------------------------------------------------------------------

def _protocolo_enviado(conn, medicao_id: int):
    return conn.execute(
        "SELECT p.id, p.numero_orgao, e.enviado_em FROM protocolo_medicoes pm JOIN protocolos p ON p.id=pm.protocolo_id "
        "JOIN envios e ON e.id=p.envio_id WHERE pm.medicao_id=? AND p.situacao='enviado' AND p.etapa IN ('nota','unico') "
        "ORDER BY p.id DESC LIMIT 1", (medicao_id,)).fetchone()


def _ultimo_protocolo(conn, medicao_id: int):
    return conn.execute("SELECT id, data, numero_processo FROM medicao_protocolos WHERE medicao_id=? "
                        "ORDER BY id DESC LIMIT 1", (medicao_id,)).fetchone()


def aguardando_pagamento(conn) -> list[dict]:
    out = []
    for r in conn.execute(
            "SELECT m.*, c.nome_curto, c.numero_instrumento, o.familia, o.chave AS orgao_chave, o.nome AS orgao_nome "
            "FROM medicoes m JOIN contratos c ON c.id=m.contrato_id LEFT JOIN orgaos o ON o.id=c.orgao_id "
            "WHERE m.estado='protocolada'"):
        p = _protocolo_enviado(conn, r["id"])
        mp = _ultimo_protocolo(conn, r["id"])
        if r["envio_origem"] == "externo":
            enviada = r["envio_externo_em"]
        elif p:
            enviada = tempo.para_local(datetime.datetime.fromisoformat(p["enviado_em"])).date().isoformat()
        else:
            enviada = mp["data"][:10] if mp else None
        numero = (p["numero_orgao"] if p else None) or (mp["numero_processo"] if mp else None)
        out.append({"medicao_id": r["id"], "contrato_id": r["contrato_id"],
                    "obra": r["nome_curto"] or r["numero_instrumento"],
                    "orgao": _grupo(r["familia"], {"chave": r["orgao_chave"], "nome": r["orgao_nome"]})
                    if r["familia"] else None,
                    "descricao": medicoes.titulo(r).replace("Medição", "medição"),
                    "valor_centavos": r["valor_protocolado_centavos"], "enviada_em": enviada, "numero_orgao": numero,
                    "familia": r["familia"], "origem": r["envio_origem"] or ("sistema" if p else None),
                    "protocolo_id": p["id"] if p else None,
                    "sem_numero_orgao": r["familia"] == "mtpar" and not numero})
    return sorted(out, key=lambda x: (x["enviada_em"] or "", x["medicao_id"]), reverse=True)


def registrar_numero_orgao(conn, usuario_id: int, medicao_id: int, numero: str) -> None:
    """D10: nº do SIGA (MTPAR). Envio pelo sistema: no protocolo; feito por fora: no registro do protocolo."""
    numero = (numero or "").strip()
    if not numero:  # A-15 (10/10/2026): vazio apagava o numero gravado; nao ha' "apagar" na tela
        raise ValueError(protocolo.NUMERO_ORGAO_VAZIO)
    p = _protocolo_enviado(conn, medicao_id)
    if p:
        protocolo.registrar_numero_orgao(conn, usuario_id, p["id"], numero, None)
        return
    mp = _ultimo_protocolo(conn, medicao_id)
    if mp is None:
        raise ValueError("Medição sem envio registrado")
    with db.mutacao(conn):
        conn.execute("UPDATE medicao_protocolos SET numero_processo=? WHERE id=?", (numero, mp["id"]))
        auditoria.registrar(conn, usuario_id, "medicao.numero_orgao", "medicao", medicao_id,
                            {"numero_processo": mp["numero_processo"]}, {"numero_processo": numero})
