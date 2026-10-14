"""Protocolo de medicao feito pelo sistema (bloco 5; spec 2026-09-21 §3 passos 4 a 7, §5.3, §5.4, §6).

Um PROTOCOLO e' um documento a assinar e um oficio. A FAMILIA do orgao decide as ETAPAS (SINFRA tem
duas: medicao assinada e nota), as PARTES do PDF e os anexos SOLTOS do e-mail; o CADASTRO do orgao
decide destinatarios, textos, pecas tecnicas e sua ordem, ordem das certidoes e limite por documento.

Ciclo: rascunho -> montado (PDF gerado para assinar) -> assinado (PDF do DocuSign conferido) ->
enviado (e-mail aceito). Descartado sai do ciclo. O que falta vira PENDENCIA (avisa e deixa seguir);
so' bloqueia o que e' erro (medicao encerrada, sem destinatario, anexos acima do teto do e-mail).
"""
import datetime
import json
import os
import re
from dataclasses import dataclass
from html import escape

from app import (arquivos, assinatura, auditoria, carta, cadastro_arquivos, certidoes, checklist, correio, db,
                 documentos, envio_reserva, espelhos, frc, leitura_pdf, medicoes, oficios, pdfs, tempo)

TIPOS_PECA = cadastro_arquivos.TIPOS_PECA
ROTULO_NATUREZA = {"execucao": "Medição", "projeto": "Projeto", "reajuste": "Reajuste"}
ENCERRADAS = ("cancelada", "desistida", "recebida")
SEM_NOTA = ("prevista", "espelho_gerado", "espelho_enviado")
MIN_JUSTIFICATIVA = 10           # enviar com pendencia exige uma frase, nao "." (gate Sol do bloco 5)
# 09/10/2026: documento extra do envio (ex.: justificativa tecnica). Vai SEMPRE solto no e-mail, em qualquer orgao,
# nunca dentro do PDF da carta -- por isso anexar ou remover nao desfaz o montado/assinado.
ANEXO = "anexo"
JUSTIFICATIVA_POS_ENVIO = "Pendência surgida entre a prévia e o envio; o e-mail já tinha saído"
NUMERO_ORGAO_VAZIO = "Informe o número do protocolo no órgão"
# A-13 (testes de quebra 10/10/2026): o link vira <a href> no e-mail oficial ao orgao; so' o OneDrive e o SharePoint
# da Lotufo. Comparacao exata do host: "...sharepoint.com.evil.test" nao passa. Issue #118: os hosts vem de
# DASH_SHAREPOINT_HOSTS (separados por virgula; repositorio publico); sem a variavel, nenhum link passa.
VARIAVEL_HOSTS_LINK = "DASH_SHAREPOINT_HOSTS"


def dominios_link() -> tuple[str, ...]:
    return tuple(h for h in (x.strip().lower() for x in os.environ.get(VARIAVEL_HOSTS_LINK, "").split(",")) if h)


@dataclass(frozen=True)
class Etapa:
    chave: str                  # 'unico' | 'medicao' | 'nota'
    rotulo: str
    carta: bool                 # gera carta e passa pela assinatura
    capa: bool                  # SES: pagina "42ª MEDIÇÃO / PERÍODO"
    divisorias: bool            # SES: pagina de titulo antes de cada secao
    partes: tuple[str, ...]     # ordem do PDF: 'carta', 'notas', 'certidoes', 'pecas'
    soltos: tuple[str, ...]     # anexos do e-mail fora do PDF: 'planilha', 'notas', 'certidoes_zip', 'cno',
                                # 'regularidade', 'pecas_soltas'
    marca_protocolada: bool
    junta_naturezas: bool       # execucao e reajuste no mesmo e-mail (cada um no seu PDF)


FAMILIAS: dict[str, tuple[Etapa, ...]] = {
    "mtpar": (Etapa("unico", "Protocolo", True, False, False, ("carta", "notas", "certidoes"), (), True, False),),
    "ses": (Etapa("unico", "Protocolo", True, True, True, ("carta", "notas", "certidoes", "pecas"), (), True, False),),
    "sinfra": (Etapa("medicao", "Medição assinada", True, False, False, ("carta", "pecas"), ("planilha",), False, True),
               # D5 (09/10/2026): sem a ficha do CNO; relatorios assinados (BRT, SACID) vao soltos quando anexados.
               Etapa("nota", "Nota, certidões e regularidade", False, False, False, (),
                     ("notas", "certidoes_zip", "regularidade", "pecas_soltas"), True, True)),
    "prefeitura": (Etapa("unico", "Protocolo", True, False, False, ("carta", "notas"),
                         ("certidoes_zip", "pecas_soltas"), True, False),),
}


# --- leitura ---------------------------------------------------------------------------------------

def _contrato(conn, contrato_id: int) -> dict:
    c = conn.execute("SELECT * FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    if c is None:
        raise ValueError(f"Contrato {contrato_id} não encontrado")
    return dict(c)


def _orgao(conn, c: dict) -> tuple[str, dict, dict]:
    if not c.get("orgao_id"):
        raise ValueError("Contrato sem órgão no cadastro: não há família de protocolo")
    o = conn.execute("SELECT * FROM orgaos WHERE id=?", (c["orgao_id"],)).fetchone()
    return o["familia"], json.loads(o["regras"] or "{}"), dict(o)


def etapas_do_contrato(conn, contrato_id: int) -> list[Etapa]:
    familia, _, _ = _orgao(conn, _contrato(conn, contrato_id))
    return list(FAMILIAS[familia])


def _etapa(familia: str, chave: str) -> Etapa:
    for e in FAMILIAS[familia]:
        if e.chave == chave:
            return e
    raise ValueError(f"A família {familia} não tem a etapa {chave!r}")


def _junta_do_orgao(regras: dict, o: dict) -> bool:
    """D9 (09/10/2026): orgao que recebe medicao e reajuste no mesmo e-mail e no mesmo oficio (Pref. VG, CT-254).
    Regra `junta_naturezas` do cadastro; sem ela, a Pref. VG junta e as demais seguem a familia."""
    return bool(regras.get("junta_naturezas", o.get("chave") == "pref-vg"))


def junta_naturezas(regras: dict, o: dict, e: Etapa) -> bool:
    return e.junta_naturezas or _junta_do_orgao(regras, o)


class Bloqueio(ValueError):
    """D8: o que impede o envio sem justificativa possivel (certidao vencida)."""


titulo = medicoes.titulo          # bloco 6: o titulo mora em `medicoes` (lista de medicoes em andamento)


def _obra(c: dict) -> str:
    return c.get("nome_curto") or c.get("numero_instrumento") or ""


def _medicoes(conn, protocolo_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT m.* FROM protocolo_medicoes pm JOIN medicoes m ON m.id=pm.medicao_id "
        "WHERE pm.protocolo_id=? ORDER BY m.tipo='reajuste', m.id", (protocolo_id,))]


def _periodo(conn, m: dict) -> str:
    e = conn.execute(
        "SELECT e.periodo_inicio, e.periodo_fim FROM espelho_medicoes em JOIN espelhos e ON e.id=em.espelho_id "
        "WHERE em.medicao_id=? AND e.situacao='vigente' ORDER BY e.versao DESC LIMIT 1", (m["id"],)).fetchone()
    ano, mes = int(m["competencia"][:4]), int(m["competencia"][5:7])
    ini = datetime.date(ano, mes, 1)
    fim = datetime.date(ano + (mes == 12), mes % 12 + 1, 1) - datetime.timedelta(days=1)
    if e and e["periodo_inicio"] and e["periodo_fim"]:
        ini, fim = datetime.date.fromisoformat(e["periodo_inicio"]), datetime.date.fromisoformat(e["periodo_fim"])
    return f"{ini:%d/%m/%Y} a {fim:%d/%m/%Y}"


def _docs_nota(conn, medicao_ids: list[int]) -> list[dict]:
    if not medicao_ids:
        return []
    marcas = ",".join("?" * len(medicao_ids))
    return [dict(r) for r in conn.execute(
        f"SELECT id, medicao_id, tipo_doc, nome, numero_nf, arquivo FROM medicao_documentos "
        f"WHERE medicao_id IN ({marcas}) AND tipo_doc IN ('nfs','nf','fatura') AND arquivo IS NOT NULL "
        f"ORDER BY tipo_doc='fatura', id", medicao_ids)]


def _pecas(conn, protocolo_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM protocolo_pecas WHERE protocolo_id=? AND removida_em IS NULL ORDER BY id", (protocolo_id,))]


def _bytes(rel: str) -> bytes:
    return arquivos.caminho_seguro(rel).read_bytes()


def _linha(conn, protocolo_id: int) -> dict:
    r = conn.execute("SELECT * FROM protocolos WHERE id=?", (protocolo_id,)).fetchone()
    if r is None:
        raise ValueError(f"Protocolo {protocolo_id} não encontrado")
    return dict(r)


# --- criar e pecas ---------------------------------------------------------------------------------

def criar(conn, usuario_id: int, contrato_id: int, etapa: str, medicao_ids: list[int],
          numero_oficio: str | None) -> int:
    c = _contrato(conn, contrato_id)
    familia, regras, o = _orgao(conn, c)
    e = _etapa(familia, etapa)
    ids = sorted(set(medicao_ids or []))
    if not ids:
        raise ValueError("Escolha ao menos uma medição")
    ms = [dict(r) for r in conn.execute(f"SELECT * FROM medicoes WHERE id IN ({','.join('?' * len(ids))})", ids)]
    if len(ms) != len(ids) or any(m["contrato_id"] != contrato_id for m in ms):
        raise ValueError("Medição de outro contrato")
    for m in ms:
        if m["estado"] in ENCERRADAS:
            raise ValueError(f"{titulo(m)} está {m['estado']}: não recebe protocolo")
    naturezas = {m["tipo"] for m in ms}
    # Sem carta (SINFRA, nota) nao ha oficio a separar; a Pref. VG junta no mesmo oficio (D9).
    if len(naturezas) > 1 and not (familia == "ses" or (e.junta_naturezas and not e.carta)
                                   or _junta_do_orgao(regras, o)):
        raise ValueError("Execução e reajuste vão em protocolos separados (um ofício para cada)")
    natureza = "execucao" if "execucao" in naturezas else next(iter(naturezas))
    canon = None
    if e.carta:
        sigla = conn.execute("SELECT sigla_oficio FROM entidades WHERE id=?",
                             (c["entidade_id"],)).fetchone()["sigla_oficio"] if c.get("entidade_id") else "LT"
        canon = oficios.canonico(numero_oficio or "", sigla, tempo.hoje_local().year)
    with db.mutacao(conn):
        pid = conn.execute("INSERT INTO protocolos (contrato_id, etapa, natureza, numero_oficio, usuario_id) "
                           "VALUES (?,?,?,?,?)", (contrato_id, etapa, natureza, canon, usuario_id)).lastrowid
        for mid in ids:
            conn.execute("INSERT INTO protocolo_medicoes (protocolo_id, medicao_id) VALUES (?,?)", (pid, mid))
        auditoria.registrar(conn, usuario_id, "protocolo.criar", "protocolo", pid, None,
                            {"etapa": etapa, "medicoes": ids, "numero_oficio": canon})
    return pid


def _editavel(p: dict) -> None:
    if p["situacao"] in ("enviado", "descartado"):
        raise ValueError(f"Protocolo {p['situacao']}: não pode ser alterado")


def _voltar_a_rascunho(conn, p: dict) -> None:
    """Mudou o conteudo depois de montado: o PDF montado (e o assinado) deixam de valer."""
    if p["situacao"] in ("montado", "assinado"):
        conn.execute("UPDATE protocolos SET situacao='rascunho', assinado_arquivo=NULL, assinado_sha256=NULL, "
                     "conferencia=NULL WHERE id=?", (p["id"],))


def adicionar_peca(conn, usuario_id: int, protocolo_id: int, tipo: str, nome: str, dados: bytes, ext: str) -> int:
    if tipo not in TIPOS_PECA and tipo != ANEXO:
        raise ValueError(f"Tipo de peça inválido: {tipo!r}")
    if ext not in ("pdf", "xlsx", "zip"):
        raise ValueError("A peça é um PDF ou uma planilha .xlsx")
    if ext == "zip" and tipo != ANEXO:
        raise ValueError("Arquivo .zip só entra como documento complementar do envio")
    p = _linha(conn, protocolo_id)
    _editavel(p)
    rel, sha = arquivos.gravar_bytes("protocolos", dados, ext)
    with db.mutacao(conn):
        peca_id = conn.execute(
            "INSERT INTO protocolo_pecas (protocolo_id, tipo, nome, arquivo, sha256, tamanho, ext) "
            "VALUES (?,?,?,?,?,?,?)", (protocolo_id, tipo, nome, rel, sha, len(dados), ext)).lastrowid
        if tipo != ANEXO:
            _voltar_a_rascunho(conn, p)
        auditoria.registrar(conn, usuario_id, "protocolo.peca", "protocolo", protocolo_id, None,
                            {"peca_id": peca_id, "tipo": tipo, "nome": nome, "sha256": sha})
    return peca_id


def links(conn, protocolo_id: int) -> list[dict]:
    """Arquivos por link do OneDrive (migracao 034): vao no corpo do e-mail, fora do limite dos anexos."""
    return [dict(r) for r in conn.execute(
        "SELECT id, nome, url FROM protocolo_links WHERE protocolo_id=? AND removido_em IS NULL ORDER BY id",
        (protocolo_id,))]


def adicionar_link(conn, usuario_id: int, protocolo_id: int, nome: str, url: str) -> int:
    nome, url = (nome or "").strip(), (url or "").strip()
    if not nome:
        raise ValueError("Dê um nome ao arquivo do link (ex.: Documento juntado - 15ª Medição)")
    if len(nome) > 200:
        raise ValueError("Nome do arquivo acima de 200 caracteres")
    if not re.fullmatch(r"https://\S{8,2000}", url):
        raise ValueError("Cole o link completo do OneDrive (começa com https://)")
    dominios = dominios_link()
    if not dominios:
        raise ValueError("Links do OneDrive ou SharePoint não estão liberados neste servidor: "
                         "o administrador precisa configurar os endereços permitidos")
    # O texto literal entre "https://" e a PRIMEIRA "/" tem que ser um host da lista: "\", "@" (userinfo), ":" (porta),
    # "%", "?" e "#" ficam de fora. "https://evil.test\@host/..." daria hostname=host no urlparse, mas o navegador le "\"
    # como "/" e abre evil.test. Sem urlparse: ele tambem lancaria erro em ingles para "[" ou barra Unicode.
    m = re.match(r"https://([^/]*)/", url)
    if not m or m.group(1).lower() not in dominios:
        raise ValueError(f"Cole um link do OneDrive ou SharePoint da Lotufo ({' ou '.join(dominios)})")
    p = _linha(conn, protocolo_id)
    _editavel(p)
    with db.mutacao(conn):
        link_id = conn.execute("INSERT INTO protocolo_links (protocolo_id, nome, url) VALUES (?,?,?)",
                               (protocolo_id, nome, url)).lastrowid
        auditoria.registrar(conn, usuario_id, "protocolo.link", "protocolo", protocolo_id, None,
                            {"link_id": link_id, "nome": nome, "url": url})
    return link_id


def remover_link(conn, usuario_id: int, protocolo_id: int, link_id: int) -> None:
    p = _linha(conn, protocolo_id)
    _editavel(p)
    with db.mutacao(conn):
        n = conn.execute("UPDATE protocolo_links SET removido_em=datetime('now') "
                         "WHERE id=? AND protocolo_id=? AND removido_em IS NULL", (link_id, protocolo_id)).rowcount
        if n != 1:
            raise ValueError("Link não encontrado")
        auditoria.registrar(conn, usuario_id, "protocolo.link_removido", "protocolo", protocolo_id, None,
                            {"link_id": link_id})


def remover_peca(conn, usuario_id: int, protocolo_id: int, peca_id: int) -> None:
    p = _linha(conn, protocolo_id)
    _editavel(p)
    tipo = conn.execute("SELECT tipo FROM protocolo_pecas WHERE id=? AND protocolo_id=?", (peca_id, protocolo_id)).fetchone()
    with db.mutacao(conn):
        n = conn.execute("UPDATE protocolo_pecas SET removida_em=datetime('now') "
                         "WHERE id=? AND protocolo_id=? AND removida_em IS NULL", (peca_id, protocolo_id)).rowcount
        if n != 1:
            raise ValueError("Peça não encontrada")
        if tipo[0] != ANEXO:
            _voltar_a_rascunho(conn, p)
        auditoria.registrar(conn, usuario_id, "protocolo.peca_removida", "protocolo", protocolo_id, None,
                            {"peca_id": peca_id})


# --- carta -----------------------------------------------------------------------------------------

def _config_pecas(regras: dict, natureza: str | None = None) -> list[dict]:
    """Pecas do orgao; com `natureza`, so' as que valem para ela (`naturezas` ausente = todas)."""
    out = [{"exigida": False, "solto": False, **x} for x in (regras.get("pecas") or [])]
    return [x for x in out if not natureza or not x.get("naturezas") or natureza in x["naturezas"]]


def _brl(centavos: int) -> str:
    inteiro, cent = divmod(int(centavos), 100)
    return f"{inteiro:,}".replace(",", ".") + f",{cent:02d}"


def _numeros_nf(docs: list[dict]) -> str:
    nums = [d["numero_nf"] for d in docs if d["tipo_doc"] in ("nfs", "nf") and d.get("numero_nf")]
    if nums:
        return "NF nº " + ", ".join(dict.fromkeys(nums))
    nomes = [(d["nome"] or "").rsplit(".", 1)[0] for d in docs if d["tipo_doc"] in ("nfs", "nf")]
    return ", ".join(dict.fromkeys(nomes)) or "NF"


def _lista(conn, p: dict, familia: str, regras: dict, ms: list[dict]) -> str:
    """Itens da carta: notas (numero e valor), certidoes, pecas. SES numera; as outras usam i., ii."""
    e = _etapa(familia, p["etapa"])
    itens = []
    docs = _docs_nota(conn, [m["id"] for m in ms])
    if familia == "ses":
        total = sum(m["valor_protocolado_centavos"] or 0 for m in ms)
        itens.append(f"Nota Fiscal – R$ {_brl(total)}")
    elif "notas" in e.partes:
        itens.append(f"Nota fiscal de prestação de serviços – {_numeros_nf(docs)}")
    if "certidoes" in e.partes or familia == "prefeitura":
        itens.append("Certidões de regularidade fiscal")
    presentes = {x["tipo"] for x in _pecas(conn, p["id"])}
    for cfg in _config_pecas(regras, p["natureza"]):
        if not cfg["solto"] and (cfg["exigida"] or cfg["tipo"] in presentes):
            itens.append(cfg["rotulo"])
    romanos = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]
    fim = lambda k: "." if k == len(itens) - 1 else ";"                          # noqa: E731
    if familia == "ses":
        linhas = [f"{k + 1}. {t}" for k, t in enumerate(itens)]
    elif familia == "sinfra":                      # como no CT-058: "I - ...;" e o ultimo com ponto final
        linhas = [f"{romanos[k].upper()} - {t}{fim(k)}" for k, t in enumerate(itens)]
    else:                             # como no CT-301: "i. ...;" e o ultimo com ponto final
        linhas = [f"{romanos[k]}. {t}{'.' if k == len(itens) - 1 else ';'}" for k, t in enumerate(itens)]
    if familia == "ses" and len(ms) > 1:           # "Sendo: 41ª Medição – R$ ..." logo abaixo da nota
        linhas[1:1] = [f"   Sendo: {titulo(m)} – R$ {_brl(m['valor_protocolado_centavos'] or 0)}" for m in ms]
    return "\n".join(linhas)


def _campos(conn, p: dict, c: dict, familia: str, regras: dict, ms: list[dict]) -> dict:
    em = carta.emitente(conn, c["entidade_id"]) if c.get("entidade_id") else {}
    m0 = ms[0]
    return {"razao_social": em.get("razao_social", ""), "cnpj": em.get("cnpj", ""),
            "oficio": p["numero_oficio"] or "",
            "oficio_barra": oficios.na_carta(p["numero_oficio"]) if p["numero_oficio"] else "", "medicao": " e ".join(titulo(m) for m in ms),
            # "à 23ª Medição" / "ao Reajuste da 23ª Medição" (a carta real diz "relativos a ...")
            "a_medicao": " e ".join(("ao " if m["tipo"] == "reajuste" else "à ") + titulo(m) for m in ms),
            "municipio": c.get("municipio") or "Cuiabá",
            "numero": f"{m0['numero']}ª", "numero_extenso": carta.ordinal_extenso(m0["numero"]),
            "periodo": _periodo(conn, m0), "competencia": f"{m0['competencia'][5:7]}/{m0['competencia'][:4]}",
            "obra": _obra(c), "instrumento": c.get("numero_instrumento") or "",
            "objeto": carta.objeto_na_frase(carta.objeto_do_contrato(c)),
            "lista": _lista(conn, p, familia, regras, ms), "saudacao": espelhos.saudacao()}


def _texto(textos: dict, chave: str, p: dict) -> str:
    """Texto da familia; protocolo so' de reajuste usa `reajuste_<chave>` quando existe (SINFRA, CT-051)."""
    return textos.get(f"reajuste_{chave}") if p["natureza"] == "reajuste" and textos.get(f"reajuste_{chave}") \
        else textos[chave]


def corpo_padrao(conn, protocolo_id: int) -> str:
    p = _linha(conn, protocolo_id)
    c = _contrato(conn, p["contrato_id"])
    familia, regras, _ = _orgao(conn, c)
    textos = carta.config(conn)["familias"][familia]
    return carta.preencher(_texto(textos, "carta_corpo", p), _campos(conn, p, c, familia, regras,
                                                                     _medicoes(conn, protocolo_id))).strip()


def _carta(conn, p: dict, corpo: str, hoje: datetime.date) -> carta.Carta:
    c = _contrato(conn, p["contrato_id"])
    familia, regras, o = _orgao(conn, c)
    cfg = carta.config(conn)
    campos = _campos(conn, p, c, familia, regras, _medicoes(conn, p["id"]))
    f = carta.fiscal_vigente(conn, c["id"], hoje.isoformat())
    ac = []
    if f:
        ac.append(f"A/C: {f['nome']}")
        cargo = f.get("cargo")
        if familia == "mtpar":            # D3 (09/10/2026): como no CT-304, a linha do fiscal abaixo do A/C
            ac.append(f"Engenheiro(a) Fiscal: {f['nome']}")
            cargo = None if cargo and "fiscal" in cargo.lower() else cargo
        ac += [x for x in (cargo, f.get("portaria")) if x]
    vocativo = {"Senhor": "Prezado Senhor,", "Senhora": "Prezada Senhora,"}.get((f or {}).get("tratamento"),
                                                                              "Prezados Senhores,")
    ref = f"Ref.: Contrato n.º {campos['instrumento']}"
    objeto = carta.objeto_do_contrato(c)
    if objeto:
        ref += f" – {objeto}"
    textos = cfg["familias"][familia]
    local = carta.preencher(textos.get("local") or "Cuiabá/MT", campos)
    return carta.Carta(numero=oficios.na_carta(p["numero_oficio"]), local_data=f"{local}, {carta.data_extenso(hoje)}.",
                       destinatario=regras.get("carta_destinatario") or [o["nome"]], ac=ac, referencia=ref,
                       assunto=carta.preencher(_texto(textos, "carta_assunto", p), campos),
                       vocativo=vocativo, corpo=corpo, assinatura=textos.get("assinatura") or cfg.get("signatario") or [],
                       emitente=carta.emitente(conn, c["entidade_id"]) if c.get("entidade_id") else {})


# --- montar ----------------------------------------------------------------------------------------

def nome_arquivo(conn, p: dict) -> str:
    """Spec §4.4: `{OFICIO} - {obra} - {nº}ª {Natureza} ({MM.AAAA}).pdf`."""
    c = _contrato(conn, p["contrato_id"])
    m = _medicoes(conn, p["id"])[0]
    doc = p["numero_oficio"] or ("NOTA" if p["etapa"] == "nota" else "PROTOCOLO")
    comp = f"{m['competencia'][5:7]}.{m['competencia'][:4]}"
    return f"{doc} - {_obra(c)} - {m['numero']:02d}ª {ROTULO_NATUREZA[p['natureza']]} ({comp}).pdf"


def _certidoes_pdf(conn, p: dict, regras: dict, hoje: datetime.date) -> list[bytes]:
    ex = documentos.exigidos(conn, p["contrato_id"], p["natureza"])
    ordem = regras.get("ordem_certidoes") or sorted(t["chave"] for t in ex["tipos"])
    tipos = sorted(ex["tipos"], key=lambda t: ordem.index(t["chave"]) if t["chave"] in ordem else 99)
    out = []
    for eid in ex["entidades"]:
        for t in tipos:
            v = certidoes.vigente(conn, eid, t["id"], hoje.isoformat())
            if v and v.get("arquivo"):
                out.append(_bytes(v["arquivo"]))
    return out


def montar(conn, usuario_id: int, protocolo_id: int, corpo: str | None = None,
           hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    p = _linha(conn, protocolo_id)
    _editavel(p)
    c = _contrato(conn, p["contrato_id"])
    familia, regras, _ = _orgao(conn, c)
    e = _etapa(familia, p["etapa"])
    if not e.carta:
        raise ValueError("Esta etapa não tem pacote para assinar: os arquivos vão soltos no e-mail")
    # Corpo vazio nao e' carta: vale o texto ja' gravado ou, na falta dele, o padrao da familia.
    corpo = (corpo or "").strip() or p["corpo_carta"] or corpo_padrao(conn, protocolo_id)
    ms = _medicoes(conn, protocolo_id)
    em = carta.emitente(conn, c["entidade_id"]) if c.get("entidade_id") else {}
    partes: list[bytes] = []
    if e.capa:
        partes.append(carta.pagina_titulo([" e ".join(titulo(m) for m in ms).upper(),
                                           f"PERÍODO: {_periodo(conn, ms[0])}"], em))
    pecas = _pecas(conn, protocolo_id)
    config_pecas = _config_pecas(regras)
    for parte in e.partes:
        if parte == "carta":
            partes.append(carta.gerar(_carta(conn, p, corpo, hoje)))
        elif parte == "notas":
            docs = _docs_nota(conn, [m["id"] for m in ms])
            if docs and e.divisorias:
                partes.append(carta.pagina_titulo(["NOTA FISCAL"], em))
            partes += [_bytes(d["arquivo"]) for d in docs]
        elif parte == "certidoes":
            certs = _certidoes_pdf(conn, p, regras, hoje)
            if certs and e.divisorias:
                partes.append(carta.pagina_titulo(["CERTIDÕES"], em))
            partes += certs
        elif parte == "pecas":
            conhecidos = set()
            for cfg in config_pecas:
                conhecidos.add(cfg["tipo"])
                das = [x for x in pecas if x["tipo"] == cfg["tipo"] and x["ext"] == "pdf" and not cfg["solto"]]
                if das and e.divisorias:
                    partes.append(carta.pagina_titulo([cfg["rotulo"].upper()], em))
                partes += [_bytes(x["arquivo"]) for x in das]
            partes += [_bytes(x["arquivo"]) for x in pecas
                       if x["ext"] == "pdf" and x["tipo"] not in conhecidos and x["tipo"] != ANEXO]
    pdf, n = leitura_pdf.juntar_com_limite(partes)
    if len(pdf) > pdfs.TETO_BYTES_PACOTE:
        raise ValueError(f"Pacote de {len(pdf) // (1024 * 1024)} MB, acima do limite de "
                         f"{pdfs.TETO_BYTES_PACOTE // (1024 * 1024)} MB: separe as peças")
    rel, sha = arquivos.gravar_bytes("protocolos", pdf, "pdf")
    with db.mutacao(conn):
        conn.execute("UPDATE protocolos SET corpo_carta=?, montado_arquivo=?, montado_sha256=?, montado_paginas=?, "
                     "montado_em=datetime('now'), assinado_arquivo=NULL, assinado_sha256=NULL, conferencia=NULL, "
                     "situacao='montado' WHERE id=?", (corpo, rel, sha, n, protocolo_id))
        auditoria.registrar(conn, usuario_id, "protocolo.montar", "protocolo", protocolo_id, None,
                            {"sha256": sha, "paginas": n, "tamanho": len(pdf)})
    return {"arquivo": rel, "sha256": sha, "paginas": n, "tamanho": len(pdf), "nome": nome_arquivo(conn, p)}


# --- pendencias, detalhe e lista -------------------------------------------------------------------

def _irmas_fora(conn, p: dict, ms: list[dict]) -> list[dict]:
    """Execucao e reajuste do mesmo numero e competencia, com nota emitida, fora deste envio. `separado`: a irma
    esta' noutro envio ainda ativo da mesma etapa (gate Sol S1, 10/10/2026: dois rascunhos nao anulam a regra). So'
    sai da conta a irma ja' enviada. Par exato execucao x reajuste (S2): projeto e' outra serie."""
    dentro = {m["id"] for m in ms}
    achadas: dict[int, dict] = {}
    for m in ms:
        for r in conn.execute(
                "SELECT x.*, EXISTS (SELECT 1 FROM protocolo_medicoes pm JOIN protocolos q ON q.id=pm.protocolo_id "
                "WHERE pm.medicao_id=x.id AND q.etapa=? AND q.situacao NOT IN ('descartado','enviado')) AS separado "
                "FROM medicoes x WHERE x.contrato_id=? AND x.numero=? AND x.competencia=? "
                "AND x.estado='nota_emitida' "
                "AND ((?='execucao' AND x.tipo='reajuste') OR (?='reajuste' AND x.tipo='execucao')) "
                "AND NOT EXISTS (SELECT 1 FROM protocolo_medicoes pm JOIN protocolos q ON q.id=pm.protocolo_id "
                "WHERE pm.medicao_id=x.id AND q.etapa=? AND q.situacao='enviado')",
                (p["etapa"], p["contrato_id"], m["numero"], m["competencia"], m["tipo"], m["tipo"], p["etapa"])):
            if r["id"] not in dentro:
                achadas[r["id"]] = dict(r)
    return list(achadas.values())


def pendencias(conn, p: dict, hoje: datetime.date) -> list[dict]:
    c = _contrato(conn, p["contrato_id"])
    familia, regras, o = _orgao(conn, c)
    e = _etapa(familia, p["etapa"])
    ms = _medicoes(conn, p["id"])
    out = []
    if "notas" in e.partes or "notas" in e.soltos:
        for m in ms:
            if m["estado"] in SEM_NOTA or not _docs_nota(conn, [m["id"]]):
                out.append({"codigo": "sem_nota", "mensagem": f"{titulo(m)}: nota fiscal não anexada"})
        # A-18 (testes de quebra 10/10/2026): onde medicao e reajuste vao juntos (D9: SINFRA, Pref. VG), a irma com
        # nota emitida que ficou fora do e-mail vira pendencia (justifica para enviar). Nao junta sozinho.
        # Depois do envio (issue #6) a cobranca acabou: o detalhe do protocolo enviado nao a repete.
        if p["situacao"] != "enviado" and junta_naturezas(regras, o, e):
            for irma in _irmas_fora(conn, p, ms):
                if irma["separado"]:
                    msg = (f"{titulo(irma)} (mesma competência) está em outro envio separado: na SINFRA e na Pref. VG "
                           "medição e reajuste vão no mesmo e-mail — junte pela opção 'Juntar outra nota desta obra' "
                           "(o outro rascunho é descartado) ou justifique")
                else:
                    msg = (f"{titulo(irma)} (mesma competência) está com nota emitida e não vai neste e-mail: junte "
                           "pela opção 'Juntar outra nota desta obra' ou justifique")
                out.append({"codigo": "irma_fora", "medicao_id": irma["id"], "mensagem": msg})
    if "certidoes" in e.partes or "certidoes_zip" in e.soltos or "regularidade" in e.soltos:
        ck = checklist.pronto_para_protocolar(conn, c["id"], p["natureza"])
        for i in ck["itens"]:
            if i["situacao"] == "pendente":
                out.append({"codigo": "certidao", "mensagem": f"{i['entidade']}: {i['tipo']} sem validade hoje"})
    presentes = {x["tipo"] for x in _pecas(conn, p["id"])}
    # Na nota (sem carta) as pecas soltas sao opcionais (relatorios assinados): nao cobram as do orgao.
    usa_pecas = "pecas" in e.partes or "planilha" in e.soltos or ("pecas_soltas" in e.soltos and e.carta)
    for cfg in _config_pecas(regras, p["natureza"]):
        if usa_pecas and cfg["exigida"] and cfg["tipo"] not in presentes:
            out.append({"codigo": "peca", "mensagem": f"{cfg['rotulo']}: não anexada"})
    if ("notas" in e.partes or "notas" in e.soltos) and c.get("entidade_id"):
        for falta in faltas_consorcio(conn, c, ms):
            out.append({"codigo": "consorcio", "mensagem": falta})
    if "cno" in e.soltos and not c.get("cno_arquivo"):
        out.append({"codigo": "cno", "mensagem": "Comprovante do CNO da obra não está no cadastro"})
    if e.carta:
        if p["situacao"] == "rascunho":
            out.append({"codigo": "nao_montado", "mensagem": "Pacote ainda não montado"})
        elif not p["assinado_arquivo"]:
            out.append({"codigo": "nao_assinado", "mensagem": "Pacote ainda não assinado"})
        else:
            for a in (json.loads(p["conferencia"] or "{}").get("avisos") or []):
                out.append({"codigo": "conferencia", "mensagem": a["mensagem"]})
        repetido = oficios.usos(conn, p["numero_oficio"], ignorar=("protocolo", p["id"])) if p["numero_oficio"] else []
        if repetido:
            out.append({"codigo": "oficio_repetido",
                        "mensagem": f"Ofício {p['numero_oficio']} já usado em {', '.join(repetido)}"})
    limite = regras.get("limite_mb_por_documento")
    rel = p["assinado_arquivo"] or p["montado_arquivo"]
    if limite and rel and arquivos.caminho_seguro(rel).stat().st_size > limite * 1024 * 1024:
        out.append({"codigo": "limite", "mensagem": f"PDF acima de {limite} MB, o limite por documento do órgão"})
    if e.marca_protocolada:
        for m in ms:
            if m["estado"] in ("protocolada", "nf_emitida"):
                out.append({"codigo": "ja_protocolada", "mensagem": f"{titulo(m)} já está protocolada"})
    return out


def faltas_consorcio(conn, c: dict, ms: list[dict]) -> list[str]:
    """Obra de consorcio: cada medicao leva a FRC ASSINADA (documento `fatura`; a FRC que a dashboard gera, sem
    assinatura, mora em `frcs` e nao conta) e a nota de cada saida esperada do espelho, casada pelo que o PDF
    traz (frc.checklist). Medicao sem espelho: a nota de cada consorciada do cadastro, como antes."""
    consorciadas = [r["nome"] for r in conn.execute(
        "SELECT e.nome FROM entidade_consorciadas ec JOIN entidades e ON e.id=ec.consorciada_id "
        "WHERE ec.consorcio_id=? ORDER BY e.id", (c["entidade_id"],))]
    if not consorciadas:
        return []
    out = []
    for m in ms:
        docs = _docs_nota(conn, [m["id"]])
        if not any(d["tipo_doc"] == "fatura" for d in docs):
            out.append(f"{titulo(m)}: FRC assinada não anexada")
        ck = frc.checklist(conn, m)
        if ck["itens"]:
            out += [f"{titulo(m)}: nota da {i['empresa']} ({i['municipio']}) não anexada"
                    for i in ck["itens"] if i["situacao"] == "falta"]
            continue
        tem = {r[0] for r in conn.execute("SELECT consorciada FROM medicao_documentos WHERE medicao_id=? "
                                          "AND tipo_doc IN ('nfs','nf') AND arquivo IS NOT NULL", (m["id"],))}
        out += [f"{titulo(m)}: nota da {nome} não anexada" for nome in consorciadas if nome not in tem]
    return out


def certidoes_vencidas(conn, p: dict, hoje: datetime.date) -> list[str]:
    """D8: certidao exigida vencida de qualquer empresa do envio ("Lotufo: municipal vencida em 05/10/2026")."""
    _, _, e, c = _contexto(conn, p)
    if not ("certidoes" in e.partes or "certidoes_zip" in e.soltos):
        return []
    ex = documentos.exigidos(conn, c["id"], p["natureza"])
    out = []
    for eid in ex["entidades"]:
        ent = conn.execute("SELECT nome, nome_curto FROM entidades WHERE id=?", (eid,)).fetchone()
        for t in ex["tipos"]:
            s = documentos.situacao(conn, eid, t, hoje)
            if s["situacao"] == "vencida":
                out.append(f"{ent['nome_curto'] or ent['nome']}: {documentos.ROTULO.get(t['chave'], t['nome'])} "
                           f"vencida em {datetime.date.fromisoformat(s['certidao']['validade']):%d/%m/%Y}")
    return out


def bloqueio(conn, p: dict, hoje: datetime.date) -> str | None:
    vencidas = certidoes_vencidas(conn, p, hoje)
    return ("Certidão vencida — renove antes de enviar: " + "; ".join(vencidas)) if vencidas else None


def detalhe(conn, protocolo_id: int, hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    p = _linha(conn, protocolo_id)
    c = _contrato(conn, p["contrato_id"])
    familia, _, _ = _orgao(conn, c)
    e = _etapa(familia, p["etapa"])
    # A6 (mapa de 2026-09-28): quando o protocolo foi enviado e quem enviou (o dono do envio no Outlook).
    envio = conn.execute("SELECT e.enviado_em, u.nome FROM envios e LEFT JOIN usuarios u ON u.id=e.usuario_id "
                         "WHERE e.id=?", (p["envio_id"],)).fetchone() if p["envio_id"] else None
    return {**p, "familia": familia, "etapa_rotulo": e.rotulo, "tem_carta": e.carta,
            "medicoes": [{**m, "titulo": titulo(m)} for m in _medicoes(conn, protocolo_id)],
            "pecas": _pecas(conn, protocolo_id), "conferencia": json.loads(p["conferencia"] or "null"),
            "pendencias": pendencias(conn, p, hoje),
            "nome_arquivo": nome_arquivo(conn, p) if p["montado_arquivo"] else None,
            "enviado_em": envio["enviado_em"] if envio else None, "enviado_por": envio["nome"] if envio else None}


def listar(conn, contrato_id: int) -> dict:
    c = _contrato(conn, contrato_id)
    familia, regras, _ = _orgao(conn, c)
    ms = [dict(r) for r in conn.execute(
        "SELECT * FROM medicoes WHERE contrato_id=? AND estado NOT IN ('cancelada','desistida','recebida','prevista') "
        "ORDER BY numero DESC, tipo", (contrato_id,))]
    ids = [r[0] for r in conn.execute("SELECT id FROM protocolos WHERE contrato_id=? AND situacao<>'descartado' "
                                      "ORDER BY id DESC", (contrato_id,))]
    return {"familia": familia,
            "etapas": [{"chave": e.chave, "rotulo": e.rotulo, "carta": e.carta} for e in FAMILIAS[familia]],
            "pecas": _config_pecas(regras), "medicoes": [{**m, "titulo": titulo(m)} for m in ms],
            "protocolos": [detalhe(conn, i) for i in ids]}


# --- assinado, previa, envio -----------------------------------------------------------------------

def receber_assinado(conn, usuario_id: int, protocolo_id: int, pdf: bytes) -> dict:
    p = _linha(conn, protocolo_id)
    _editavel(p)
    if not p["montado_arquivo"]:
        raise ValueError("Monte o pacote antes de anexar o assinado")
    conf = assinatura.conferir_pdfs(_bytes(p["montado_arquivo"]), pdf)
    rel, sha = arquivos.gravar_bytes("protocolos", pdf, "pdf")
    with db.mutacao(conn):
        conn.execute("UPDATE protocolos SET assinado_arquivo=?, assinado_sha256=?, assinado_em=datetime('now'), "
                     "conferencia=?, situacao='assinado' WHERE id=?", (rel, sha, json.dumps(conf), protocolo_id))
        auditoria.registrar(conn, usuario_id, "protocolo.assinado", "protocolo", protocolo_id, None,
                            {"sha256": sha, "conferencia": conf})
    return detalhe(conn, protocolo_id)


def _contexto(conn, p: dict) -> tuple[str, dict, Etapa, dict]:
    c = _contrato(conn, p["contrato_id"])
    familia, regras, _ = _orgao(conn, c)
    return familia, regras, _etapa(familia, p["etapa"]), c


def _anexos(conn, p: dict, hoje: datetime.date) -> list[tuple[str, bytes]]:
    return [(n, b) for n, b, _ in _anexos_rotulados(conn, p, hoje)]


def _anexos_rotulados(conn, p: dict, hoje: datetime.date) -> list[tuple[str, bytes, str]]:
    """(nome, bytes, origem): 'pacote', 'planilha', 'pecas', 'nota', 'frc', 'certidoes', 'cno', 'regularidade'."""
    _, regras, e, c = _contexto(conn, p)
    out = []
    if e.carta and (p["assinado_arquivo"] or p["montado_arquivo"]):
        out.append((nome_arquivo(conn, p), _bytes(p["assinado_arquivo"] or p["montado_arquivo"]), "pacote"))
    pecas = _pecas(conn, p["id"])
    tipos_soltos = {x["tipo"] for x in _config_pecas(regras) if x["solto"]}
    ex = None
    for solto in e.soltos:
        if solto == "planilha":
            out += [(x["nome"], _bytes(x["arquivo"]), "planilha") for x in pecas if x["tipo"] == "planilha"]
        elif solto == "pecas_soltas":       # sem carta (nota SINFRA) toda peca anexada vai solta
            out += [(x["nome"], _bytes(x["arquivo"]), "pecas") for x in pecas
                    if x["tipo"] != ANEXO and (x["tipo"] in tipos_soltos or not e.carta)]
        elif solto == "notas":
            docs = _docs_nota(conn, [m["id"] for m in _medicoes(conn, p["id"])])
            out += [(d["nome"], _bytes(d["arquivo"]), "frc" if d["tipo_doc"] == "fatura" else "nota") for d in docs]
        elif solto == "certidoes_zip":
            ex = ex or documentos.exigidos(conn, p["contrato_id"], p["natureza"])
            for eid in ex["entidades"]:
                try:
                    out.append((*documentos.zip_vigentes(conn, eid, hoje.isoformat()), "certidoes"))
                except ValueError:
                    pass            # empresa sem nenhuma vigente: ja' e' pendencia 'certidao'
        elif solto == "cno" and c.get("cno_arquivo"):
            out.append((f"CNO - {_obra(c)}.pdf", _bytes(c["cno_arquivo"]), "cno"))
        elif solto == "regularidade":
            ex = ex or documentos.exigidos(conn, p["contrato_id"], p["natureza"])
            r = documentos.regularidade_vigente(conn, ex["regularidade"]) if ex["regularidade"] else None
            if r:           # D4 (09/10/2026): "Regularidade mensal - Lotufo - 07-2026.pdf"
                ent = conn.execute("SELECT nome, nome_curto FROM entidades WHERE id=?", (r["entidade_id"],)).fetchone()
                nome = f"Regularidade mensal - {ent['nome_curto'] or ent['nome']} - " \
                       f"{r['competencia'][5:7]}-{r['competencia'][:4]}.pdf"
                out.append((nome, _bytes(r["arquivo"]), "regularidade"))
    out += [(x["nome"], _bytes(x["arquivo"]), "anexo") for x in pecas if x["tipo"] == ANEXO]
    return out


def _e_lista(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def lista_anexos(conn, ps: list[dict], anexos: list[tuple[str, bytes, str]]) -> str:
    """D2 (09/10/2026): "notas fiscais, certidões de regularidade e regularidade mensal" -- so' o que vai."""
    _, regras, e, _ = _contexto(conn, ps[0])
    origens = [o for _, _, o in anexos]
    docs = _docs_nota(conn, [m["id"] for p in ps for m in _medicoes(conn, p["id"])]) \
        if ("notas" in e.partes and "pacote" in origens) or "nota" in origens or "frc" in origens else []
    n_nf = sum(d["tipo_doc"] != "fatura" for d in docs)
    n_frc = sum(d["tipo_doc"] == "fatura" for d in docs)
    itens = ["ofício"] if "pacote" in origens else []
    if n_nf:
        itens.append("nota fiscal" if n_nf == 1 else "notas fiscais")
    if n_frc:
        itens.append("fatura de recebimento de consórcio" if n_frc == 1 else "faturas de recebimento de consórcio")
    if "certidoes" in origens or ("certidoes" in e.partes and "pacote" in origens):
        itens.append("certidões" if n_frc else "certidões de regularidade")
    if "regularidade" in origens:
        itens.append("regularidade mensal")
    if "pecas" in origens:
        if e.carta:
            rotulos = {x["tipo"]: x["rotulo"] for x in _config_pecas(regras)}
            tipos = {x["tipo"] for p in ps for x in _pecas(conn, p["id"])}
            itens += [rotulos[t][:1].lower() + rotulos[t][1:] for t in rotulos if t in tipos and t != "planilha"]
        else:
            itens.append("relatórios assinados")
    if "planilha" in origens:
        itens.append("planilha editável")
    if "anexo" in origens:
        itens.append("documento complementar" if origens.count("anexo") == 1 else "documentos complementares")
    return _e_lista(itens) if itens else "arquivos"


def _destinatarios(conn, regras: dict, e: Etapa, c: dict, hoje: datetime.date) -> tuple[list, list]:
    chave = "protocolo_assinados_para" if e.chave == "nota" and regras.get("protocolo_assinados_para") \
        else "protocolo_para"
    para = [str(x).lower() for x in (regras.get(chave) or [])]
    if chave == "protocolo_assinados_para":     # nota da SINFRA (SUEF I/II, SUPU): so' o protocolo, sem fiscal
        return para, [str(x).lower() for x in (regras.get("protocolo_copia") or [])]
    f = carta.fiscal_vigente(conn, c["id"], hoje.isoformat())
    if f and f["email"] not in para:
        para.append(f["email"])
    para += [x for x in json.loads(c.get("destinatarios_extras") or "[]") if x not in para]
    return para, [str(x).lower() for x in (regras.get("protocolo_copia") or [])]


def previa_envio(conn, protocolo_ids: list[int], remetente: str | None = None,
                 hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    ps = [_linha(conn, i) for i in protocolo_ids]
    if not ps:
        raise ValueError("Escolha ao menos um protocolo")
    familia, regras, e, c = _contexto(conn, ps[0])
    if any((x["contrato_id"], x["etapa"]) != (ps[0]["contrato_id"], ps[0]["etapa"]) for x in ps):
        raise ValueError("Só protocolos do mesmo contrato e da mesma etapa vão no mesmo e-mail")
    if len(ps) > 1 and not junta_naturezas(regras, _orgao(conn, c)[2], e):
        raise ValueError("Nesta família cada protocolo vai no seu e-mail")
    textos = carta.config(conn)["familias"][familia]
    campos = _campos(conn, ps[0], c, familia, regras, [m for x in ps for m in _medicoes(conn, x["id"])])
    k_assunto, k_corpo = ("nota_email_assunto", "nota_email_corpo") if e.chave == "nota" else \
        ("email_assunto", "email_corpo")
    para, copia = _destinatarios(conn, regras, e, c, hoje)
    if remetente:       # o e-mail de login e a conta do Outlook (podem ser diferentes: Leo)
        fora = {remetente.lower()} | correio.contas_do_usuario(conn, remetente)
        copia = [x for x in copia if x.lower() not in fora]
    anexos = [a for x in ps for a in _anexos_rotulados(conn, x, hoje)]
    campos["lista_anexos"] = lista_anexos(conn, ps, anexos)
    total = sum(len(b) for _, b, _ in anexos)
    bloqueios = [b for x in ps if (b := bloqueio(conn, x, hoje))]
    # S1: a irma que esta' noutro protocolo DESTE MESMO e-mail ja' vai junto -- nao e' pendencia.
    juntas = {m["id"] for x in ps for m in _medicoes(conn, x["id"])}
    pend = [{"protocolo_id": x["id"], **q} for x in ps for q in pendencias(conn, x, hoje)
            if not (q["codigo"] == "irma_fora" and q["medicao_id"] in juntas)]
    if total > correio.MAX_TOTAL:
        pend.append({"protocolo_id": None, "codigo": "tamanho",
                     "mensagem": f"Anexos somam {total // (1024 * 1024)} MB, acima do limite do e-mail "
                                 f"({correio.MAX_TOTAL // (1024 * 1024)} MB): troque o maior anexo por um link "
                                 f"do OneDrive em Documentos complementares, ou envie um protocolo por e-mail"})
    corpo = carta.preencher(textos.get(k_corpo, ""), campos).strip()
    por_link = [x for p in ps for x in links(conn, p["id"])]
    if por_link:        # antes da assinatura ("Atenciosamente,"), como o Outlook poe o link do OneDrive
        bloco = "Arquivos por link (OneDrive):\n" + "\n".join(f"{x['nome']}: {x['url']}" for x in por_link)
        partes = corpo.rsplit("\n\n", 1)
        corpo = f"{partes[0]}\n\n{bloco}\n\n{partes[1]}" if len(partes) == 2 else f"{corpo}\n\n{bloco}"
    return {"para": para, "copia": copia, "assunto": carta.preencher(textos.get(k_assunto, ""), campos),
            "corpo": corpo, "links": por_link,
            "anexos": [{"nome": n, "tamanho": len(b), "origem": o} for n, b, o in anexos], "total": total,
            "limite": correio.MAX_TOTAL, "pendencias": pend, "bloqueio": " · ".join(dict.fromkeys(bloqueios)) or None}


_URL = re.compile(r"https://[^\s<>\"]+")


def _html(corpo: str) -> str:
    # link (OneDrive) clicavel: o texto ja' escapado so' tem &amp; no lugar de &, que o href aceita
    def par(texto: str) -> str:
        t = escape(texto)
        return _URL.sub(lambda m: f'<a href="{m.group(0)}">{m.group(0)}</a>', t).replace(chr(10), "<br>")
    return "".join(f"<p>{par(p)}</p>" for p in corpo.strip().split("\n\n"))


def _oficio_da_medicao(conn, medicao_id: int) -> str | None:
    r = conn.execute("SELECT p.numero_oficio FROM protocolo_medicoes pm JOIN protocolos p ON p.id=pm.protocolo_id "
                     "WHERE pm.medicao_id=? AND p.situacao='enviado' AND p.numero_oficio IS NOT NULL "
                     "ORDER BY p.id DESC LIMIT 1", (medicao_id,)).fetchone()
    return r[0] if r else None


def enviar(conn, usuario: dict, protocolo_ids: list[int], para: list[str], copia: list[str], assunto: str,
           corpo: str, justificativa: str | None = None, hoje: datetime.date | None = None,
           cco: list[str] | None = None, anexos_previa: list[dict] | None = None) -> int:
    hoje = hoje or tempo.hoje_local()
    ps = [_linha(conn, i) for i in protocolo_ids]
    pv = previa_envio(conn, protocolo_ids, hoje=hoje)
    _, _, e, _ = _contexto(conn, ps[0])
    # Tudo o que recusa vem ANTES do e-mail (que nao se desfaz).
    for x in ps:
        if x["situacao"] in ("enviado", "descartado"):
            raise ValueError(f"Protocolo {x['id']} já {x['situacao']}")
        if e.carta and not x["montado_arquivo"]:
            raise ValueError("Monte o pacote antes de enviar")
        for m in _medicoes(conn, x["id"]):
            if m["estado"] in ENCERRADAS:
                raise ValueError(f"{titulo(m)} está {m['estado']}")
    para = [x.strip() for x in para if x.strip()]
    if not para:
        raise ValueError("Informe ao menos um destinatário")
    if pv["total"] > correio.MAX_TOTAL:
        raise ValueError("Anexos acima do limite do e-mail: envie um protocolo por e-mail")
    if pv["bloqueio"]:
        raise Bloqueio(pv["bloqueio"])
    # Issue #10: o e-mail leva os anexos que a pessoa conferiu na previa; documento anexado ou trocado depois dela
    # (na medicao ou no protocolo) recusa o envio em vez de sair sem ser visto.
    if anexos_previa is not None and sorted((a["nome"], a["tamanho"]) for a in anexos_previa) !=             sorted((a["nome"], a["tamanho"]) for a in pv["anexos"]):
        raise ValueError("Os anexos mudaram depois da prévia: descarte esta prévia e abra outra para conferir "
                         "o que vai no e-mail")
    justificativa = (justificativa or "").strip() or None
    if pv["pendencias"] and len(justificativa or "") < MIN_JUSTIFICATIVA:
        raise ValueError(f"{len(pv['pendencias'])} pendência(s) na prévia: informe a justificativa "
                         f"(ao menos {MIN_JUSTIFICATIVA} caracteres) para enviar assim")
    # Reserva atomica antes do e-mail (A-02, 10/10/2026): dois cliques simultaneos nao mandam dois e-mails.
    # Todos os protocolos do e-mail numa transacao so': se um ja' esta' em envio, nenhum fica reservado.
    with db.mutacao(conn):
        for x in ps:
            envio_reserva.reservar(conn, "protocolos", x["id"], usuario["id"], x["envio_id"])
    try:
        anexos = [a for x in ps for a in _anexos(conn, x, hoje)]
        envio_id = correio.enviar_e_registrar(conn, usuario, "protocolo", para,
                                              [x.strip() for x in copia if x.strip()], assunto, _html(corpo),
                                              anexos, cco=cco)
    except correio.EnvioNaoRegistrado:
        raise                                       # o e-mail saiu: a reserva fica e segura a repeticao
    except Exception:
        for x in ps:                                # nada saiu: destrava e sobe o erro original
            envio_reserva.liberar_com_retentativa(conn, "protocolos", x["id"])
        raise
    # O e-mail ja' saiu: daqui para baixo nada pode recusar (gate Sol do bloco 5). Certidao que venceu entre a
    # previa e o envio, ou medicao encerrada por outra pessoa no meio, nao desfazem o registro do envio: a
    # medicao que nao pode ser marcada fica anotada na auditoria do protocolo.
    with correio.depois_do_envio(assunto, para, envio_id), db.mutacao(conn):
        for x in ps:
            envio_reserva.liberar(conn, "protocolos", x["id"])
            conn.execute("UPDATE protocolos SET envio_id=?, situacao='enviado', justificativa=? WHERE id=?",
                         (envio_id, justificativa, x["id"]))
            nao_marcadas = []
            for m in _medicoes(conn, x["id"]):
                conn.execute("INSERT OR IGNORE INTO envio_medicoes (envio_id, medicao_id) VALUES (?,?)",
                             (envio_id, m["id"]))
                if e.marca_protocolada:
                    oficio = x["numero_oficio"] or _oficio_da_medicao(conn, m["id"])
                    # Gate Sol S6: sem pendencia na previa a justificativa e' opcional e pode ser curta; a marcacao
                    # exige o minimo e, depois do e-mail, nao pode recusar -- curta vira o texto padrao.
                    longa = justificativa if len(justificativa or "") >= MIN_JUSTIFICATIVA else None
                    try:
                        medicoes.registrar_protocolo(conn, usuario["id"], m["id"], hoje.isoformat(), oficio, None,
                                                     "manual", apesar_das_pendencias=True,
                                                     justificativa=longa or JUSTIFICATIVA_POS_ENVIO,
                                                     protocolo_id=x["id"])
                        conn.execute("UPDATE medicoes SET envio_origem='sistema' WHERE id=?", (m["id"],))
                    except ValueError as erro:
                        nao_marcadas.append({"medicao_id": m["id"], "motivo": str(erro)})
            auditoria.registrar(conn, usuario["id"], "protocolo.enviar", "protocolo", x["id"], None,
                                {"envio_id": envio_id, "pendencias": pv["pendencias"], "justificativa": justificativa,
                                 **({"nao_marcadas": nao_marcadas} if nao_marcadas else {})})
    return envio_id


def registrar_numero_orgao(conn, usuario_id: int, protocolo_id: int, numero: str,
                           comprovante: bytes | None) -> None:
    p = _linha(conn, protocolo_id)
    if p["situacao"] != "enviado":
        raise ValueError("Só protocolo enviado recebe o número do órgão")
    # A-15 (testes de quebra 10/10/2026): vazio gravava NULL e apagava o numero sem aviso. A tela nao oferece
    # apagar; vazio e' erro, e o comprovante nao e' gravado antes da recusa. Gate Sol S1: vazio COM comprovante,
    # e o numero ja' gravado, e' "anexar so' o comprovante" -- o numero fica.
    numero = (numero or "").strip()
    if not numero:
        if not comprovante:
            raise ValueError(NUMERO_ORGAO_VAZIO)
        if not p["numero_orgao"]:
            raise ValueError("Informe o número do protocolo junto com o comprovante")
        numero = p["numero_orgao"]
    rel = arquivos.gravar_bytes("protocolos", comprovante, "pdf")[0] if comprovante else p["comprovante_arquivo"]
    with db.mutacao(conn):
        conn.execute("UPDATE protocolos SET numero_orgao=?, comprovante_arquivo=? WHERE id=?",
                     (numero, rel, protocolo_id))
        auditoria.registrar(conn, usuario_id, "protocolo.numero_orgao", "protocolo", protocolo_id,
                            {"numero_orgao": p["numero_orgao"], "comprovante": p["comprovante_arquivo"]},
                            {"numero_orgao": numero, "comprovante": rel})


def descartar(conn, usuario_id: int, protocolo_id: int, motivo: str) -> None:
    p = _linha(conn, protocolo_id)
    if p["situacao"] == "enviado":
        raise ValueError("Protocolo enviado não se descarta")
    if not (motivo or "").strip():
        raise ValueError("Informe o motivo")
    with db.mutacao(conn):
        conn.execute("UPDATE protocolos SET situacao='descartado' WHERE id=?", (protocolo_id,))
        auditoria.registrar(conn, usuario_id, "protocolo.descartar", "protocolo", protocolo_id,
                            {"situacao": p["situacao"]}, {"situacao": "descartado", "motivo": motivo.strip()})
