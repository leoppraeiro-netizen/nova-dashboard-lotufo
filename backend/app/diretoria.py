"""Tela da diretoria (spec 2026-09-21 §10.5), bloco 8. Tudo na COTA da Lotufo; vocabulario fixo: medido,
faturado (nota emitida), protocolado, recebido. O total a receber (valor do protocolado e o recebimento
previsto) so' aparece com o cadastro liberando (`geral.yaml: diretoria.total_a_receber_liberado`), depois da
conciliacao com a controladoria.

Corte de 2026-09-25 (decisao do Leonardo): o faturado ate o QDOP de 22/09/2026 conta como pago, menos o que o RM
mostra em aberto. O "a receber" soma as medicoes protocoladas e as cobrancas do RM ainda nao pagas que nenhuma
medicao em aberto representa (`_notas_em_aberto`), com a idade contada da emissao da nota.

Valor de uma medicao: o atestado quando houver, senao o protocolado (a mesma regra do "medido" dos paineis),
convertido para a cota uma vez, com o arredondamento unico de `contratos.cota`.
"""
import datetime
import json
import math
from decimal import ROUND_HALF_UP, Decimal

from app import avisos as _av, contratos, cronograma, qdop, reajuste, sincronizacao_rm, tempo

QUARTIL, MEDIANA, MINIMO, PADRAO_DIAS = 0.75, 0.5, 10, 30
ESPERANDO_NOTA = ("espelho_gerado", "espelho_enviado")
ESPERANDO_PROTOCOLO = ("nota_emitida",)
PROTOCOLADAS = ("protocolada", "nf_emitida")
FORA = ("cancelada", "desistida", "prevista")
FAIXAS = (("ate_30", 0, 30), ("de_31_a_60", 31, 60), ("mais_60", 61, None))
TOLERANCIA_CENTAVOS = 100      # titulo pago com ate R$ 1,00 de diferenca nao e' divida (arredondamento do RM)
AVISO_NOTA_MINIMO = 1_000_000  # nota em aberto so' vira aviso a partir de R$ 10 mil na cota; o resto so' soma


def _quantil(valores: list[int], q: float) -> int:
    """Pela posicao mais proxima: o elemento de posicao ceil(q*n) na lista ordenada."""
    v = sorted(valores)
    return v[max(0, math.ceil(q * len(v)) - 1)]


def _d(iso: str | None) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(iso[:10]) if iso else None
    except ValueError:
        return None


def _medicoes(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT m.*, c.percentual_direito_bp AS pct, c.orgao_id, c.estado AS contrato_estado, "
        "COALESCE(c.nome_curto, c.numero_instrumento) AS obra, o.nome AS orgao_nome, "
        "(SELECT MIN(mp.data) FROM medicao_protocolos mp WHERE mp.medicao_id=m.id) AS protocolo_em "
        "FROM medicoes m JOIN contratos c ON c.id=m.contrato_id LEFT JOIN orgaos o ON o.id=c.orgao_id")]


def _cota(m: dict) -> int:
    valor = m["valor_atestado_centavos"] if m["valor_atestado_centavos"] is not None else m["valor_protocolado_centavos"]
    return contratos.cota(valor or 0, m["pct"]) or 0


def _prazo(ms: list[dict], orgao_id, hoje: datetime.date, quantil: float) -> int:
    desde = (hoje - datetime.timedelta(days=365)).isoformat()
    dias = [(_d(m["recebida_em"]) - _d(m["protocolo_em"])).days for m in ms
            if m["orgao_id"] == orgao_id and m["estado"] == "recebida" and _d(m["recebida_em"]) and _d(m["protocolo_em"])
            and m["recebida_em"][:10] >= desde]
    dias = [d for d in dias if d >= 0]
    return _quantil(dias, quantil) if len(dias) >= MINIMO else PADRAO_DIAS


def prazo_orgao(conn, orgao_id: int, hoje: datetime.date, quantil: float = QUARTIL) -> int:
    """Prazo normal do orgao: 3o quartil dos dias entre o primeiro protocolo e o recebimento das medicoes
    recebidas nos ultimos 12 meses; com menos de 10 amostras, 30 dias."""
    return _prazo(_medicoes(conn), orgao_id, hoje, quantil)


def _notas_em_aberto(conn) -> list[dict]:
    """Cobrancas do RM (nota ativa com titulo nao pago) que nenhuma medicao em aberto representa, no formato das
    medicoes protocoladas: nota sem medicao, ou ligada so' a medicao ja' fechada (recebida pelo corte, por
    exemplo). A obra vem da medicao ligada ou do centro de custo (atual ou anterior); consorcio sem centro, pela
    coligada. So' notas da coligada da entidade do contrato: a NFS-e da Lotufo em obra de consorcio e' repassada
    pelo consorcio e nao e' cobranca ao orgao. O valor e' o que falta do titulo (liquido), na cota."""
    em_aberto = set(ESPERANDO_NOTA + ESPERANDO_PROTOCOLO + PROTOCOLADAS)
    contr = {r["id"]: dict(r) for r in conn.execute("""
        SELECT c.id, c.percentual_direito_bp pct, c.orgao_id, c.estado, COALESCE(c.nome_curto, c.numero_instrumento) obra,
               c.centro_custo_rm, c.centros_custo_anteriores_rm, e.coligada_rm col, o.nome orgao_nome
        FROM contratos c JOIN entidades e ON e.id=COALESCE(c.entidade_id, 1) LEFT JOIN orgaos o ON o.id=c.orgao_id""")}
    por_centro, por_coligada = {}, {}
    for c in contr.values():
        centros = [c["centro_custo_rm"], *json.loads(c["centros_custo_anteriores_rm"] or "[]")]
        for cc in filter(None, (x and x.strip() for x in centros)):
            por_centro.setdefault((c["col"], cc), []).append(c["id"])
        if not (c["centro_custo_rm"] or "").strip() and c["col"] not in (None, 1):
            por_coligada.setdefault(c["col"], []).append(c["id"])
    out = []
    for n in conn.execute("SELECT * FROM notas_fiscais WHERE idmov IS NOT NULL AND situacao='ativa' AND emissao IS NOT NULL"):
        ligadas = conn.execute("""SELECT m.contrato_id, m.estado FROM nf_alocacoes a JOIN medicoes m ON m.id=a.medicao_id
                                  WHERE a.nota_id=? AND a.desfeita_em IS NULL""", (n["id"],)).fetchall()
        if any(r["estado"] in em_aberto for r in ligadas):
            continue                                        # a medicao em aberto ja' conta
        if ligadas:
            cid = ligadas[0]["contrato_id"]
        else:
            ids = por_centro.get((n["coligada"], (n["centro_custo"] or "").strip())) or por_coligada.get(n["coligada"]) or []
            cid = ids[0] if len(ids) == 1 else None
        c = contr.get(cid)
        if c is None or c["col"] != n["coligada"]:
            continue
        recebido, devido, _ = sincronizacao_rm._recebido_da_nota(conn, n["id"])
        falta = devido - recebido
        if falta <= TOLERANCIA_CENTAVOS:
            continue
        out.append({"estado": "protocolada", "tipo": "nota", "numero": n["numero"], "nf": _numero_nf(n["numero"]),
                    "valor_atestado_centavos": None, "valor_protocolado_centavos": falta, "pct": c["pct"],
                    "protocolo_em": n["emissao"], "orgao_id": c["orgao_id"], "orgao_nome": c["orgao_nome"],
                    "obra": c["obra"], "contrato_id": c["id"], "contrato_estado": c["estado"],
                    "competencia": None, "recebida_em": None})
    return out


def _numero_nf(numero) -> str:
    s = str(numero or "").strip()
    return str(int(s)) if s.isdigit() else s


def _liberado(conn) -> bool:
    r = conn.execute("SELECT valor FROM cadastro_geral WHERE chave='diretoria'").fetchone()
    return bool(json.loads(r["valor"]).get("total_a_receber_liberado")) if r else False


def _grupo(ms: list[dict], com_valor: bool = True) -> dict:
    return {"quantidade": len(ms), "valor_centavos": sum(_cota(m) for m in ms) if com_valor else None}


def _grupo_rec(ms: list[dict], com_valor: bool = True) -> dict:
    """Grupo do a receber. A14 (2026-09-28): quantas das cobrancas sao notas em aberto no RM (o resto sao
    medicoes protocoladas), para a tela nao chamar tudo de medicao."""
    return {**_grupo(ms, com_valor), "notas_rm": sum(1 for m in ms if m.get("tipo") == "nota")}


def _mes(d: datetime.date, soma: int = 0) -> str:
    total = d.year * 12 + d.month - 1 + soma
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def _ativos(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM contratos WHERE estado='ativo' ORDER BY nome_curto, id")]


def _faixas(protocoladas: list[dict], hoje: datetime.date, liberado: bool) -> dict:
    faixas = {}
    for chave, de, ate in FAIXAS:
        sel = [m for m in protocoladas if _d(m["protocolo_em"])
               and de <= (hoje - _d(m["protocolo_em"])).days and (ate is None or (hoje - _d(m["protocolo_em"])).days <= ate)]
        faixas[chave] = _grupo_rec(sel, liberado)
    return faixas


def _maior_dias(ms: list[dict], hoje: datetime.date) -> int | None:
    dias = [(hoje - _d(m["protocolo_em"])).days for m in ms if _d(m["protocolo_em"])]
    return max(dias) if dias else None


def _dinheiro(conn, ms: list[dict], hoje: datetime.date, liberado: bool, notas: list[dict] = ()) -> dict:
    protocoladas = [m for m in ms if m["estado"] in PROTOCOLADAS] + list(notas)
    faixas = _faixas(protocoladas, hoje, liberado)
    por_orgao: dict = {}
    for m in protocoladas:
        o = por_orgao.setdefault(m["orgao_id"], {"orgao": m["orgao_nome"] or "sem órgão", "ms": []})
        o["ms"].append(m)
    orgaos = []
    for orgao_id, o in por_orgao.items():
        # A4 (mapa de 2026-09-28): as faixas de cada orgao, o prazo normal dele e as obras que ele deve.
        por_obra: dict = {}
        for m in o["ms"]:
            por_obra.setdefault(m["contrato_id"], {"obra": m["obra"], "ms": []})["ms"].append(m)
        obras = [{"contrato_id": cid, "obra": x["obra"], **_grupo_rec(x["ms"], liberado), "maior_dias": _maior_dias(x["ms"], hoje)}
                 for cid, x in por_obra.items()]
        orgaos.append({"orgao_id": orgao_id, "orgao": o["orgao"], **_grupo_rec(o["ms"], liberado),
                       "maior_dias": _maior_dias(o["ms"], hoje), "faixas": _faixas(o["ms"], hoje, liberado),
                       "prazo_normal_dias": _prazo(ms, orgao_id, hoje, QUARTIL) if orgao_id else None,
                       "obras": sorted(obras, key=lambda x: -(x["maior_dias"] or 0))})
    pendentes = [(c, k) for c in _ativos(conn) for k in reajuste.ciclos(conn, c["id"], hoje)
                 if k["situacao"] == "apostilamento_pendente"]
    mes = _mes(hoje)
    return {"medido_esperando_nota": _grupo([m for m in ms if m["estado"] in ESPERANDO_NOTA]),
            "nota_esperando_protocolo": _grupo([m for m in ms if m["estado"] in ESPERANDO_PROTOCOLO]),
            "protocolado": {**_grupo_rec(protocoladas, liberado), "faixas": faixas,
                            "por_orgao": sorted(orgaos, key=lambda o: -(o["maior_dias"] or 0))},
            "recebido_mes": _grupo([m for m in ms if m["estado"] == "recebida" and (m["recebida_em"] or "")[:7] == mes]),
            # A13 (2026-09-28): um item por ciclo, o mais antigo primeiro, para A receber listar por obra (os
            # avisos da diretoria so' trazem os de mais de 90 dias)
            "reajustes_apostilamento": {"quantidade": len(pendentes),
                                        "maior_dias": max((k["dias"] for _, k in pendentes), default=None),
                                        "itens": sorted(({"contrato_id": c["id"], "obra": c["nome_curto"] or c["numero_instrumento"],
                                                          "data_base_mes": k["data_base_mes"], "dias": k["dias"]}
                                                         for c, k in pendentes), key=lambda x: -(x["dias"] or 0))}}


def _previsto(conn, mes: str, cache: dict) -> int:
    total = 0
    for c in _ativos(conn):
        if c["id"] not in cache:
            cache[c["id"]] = cronograma.previsto_efetivo(conn, c["id"])
        total += contratos.cota(cache[c["id"]].get(mes, 0), c["percentual_direito_bp"]) or 0
    return total


def _medido(ms: list[dict], mes: str) -> int:
    return sum(_cota(m) for m in ms if m["competencia"] == mes and m["estado"] not in FORA)


def _mes_ano(conn, ms: list[dict], hoje: datetime.date, cache: dict) -> dict:
    mes = _mes(hoje)
    meses_ano = [f"{hoje.year:04d}-{k:02d}" for k in range(1, hoje.month + 1)]
    return {"mes": mes, "medido_mes_centavos": _medido(ms, mes), "previsto_mes_centavos": _previsto(conn, mes, cache),
            "mesmo_mes_ano_anterior_centavos": _medido(ms, _mes(hoje, -12)),
            "acumulado_ano_centavos": sum(_medido(ms, x) for x in meses_ano),
            "previsto_ano_centavos": sum(_previsto(conn, x, cache) for x in meses_ano),
            "serie": [{"competencia": _mes(hoje, k), "medido_centavos": _medido(ms, _mes(hoje, k)),
                       "previsto_centavos": _previsto(conn, _mes(hoje, k), cache)} for k in range(-11, 1)]}


def _proximos(conn, ms: list[dict], hoje: datetime.date, liberado: bool, cache: dict,
              notas: list[dict] = ()) -> list[dict]:
    meses = [_mes(hoje, k) for k in range(6)]
    receber = dict.fromkeys(meses, 0)
    medianas: dict = {}
    for m in [*ms, *notas]:
        if m["estado"] not in PROTOCOLADAS or not _d(m["protocolo_em"]):
            continue
        if m["orgao_id"] not in medianas:
            medianas[m["orgao_id"]] = _prazo(ms, m["orgao_id"], hoje, MEDIANA)
        quando = max(_d(m["protocolo_em"]) + datetime.timedelta(days=medianas[m["orgao_id"]]), hoje)
        if _mes(quando) in receber:
            receber[_mes(quando)] += _cota(m)
    return [{"competencia": x, "faturamento_previsto_centavos": _previsto(conn, x, cache),
             "recebimento_previsto_centavos": receber[x] if liberado else None} for x in meses]


def _carteira(conn, ms: list[dict], hoje: datetime.date) -> dict:
    """Contratos ativos sem encerramento iniciado: o que ainda vai ser executado."""
    ultimos = {_mes(hoje, k) for k in range(-5, 1)}
    linhas, ritmo = [], 0
    for c in (x for x in _ativos(conn) if not x["encerramento_iniciado_em"]):
        v = contratos.vigente(conn, c["id"])
        medido = sum((m["valor_atestado_centavos"] if m["valor_atestado_centavos"] is not None
                      else m["valor_protocolado_centavos"] or 0)
                     for m in ms if m["contrato_id"] == c["id"] and m["tipo"] in ("execucao", "projeto")
                     and m["estado"] not in FORA)
        saldo = contratos.cota(v["valor_vigente_centavos"] - medido, c["percentual_direito_bp"]) or 0
        ritmo += sum(_cota(m) for m in ms if m["contrato_id"] == c["id"] and m["tipo"] in ("execucao", "projeto")
                     and m["estado"] not in FORA and m["competencia"] in ultimos)
        fim = _d(v.get("execucao_fim_vigente"))
        linhas.append({"contrato_id": c["id"], "obra": c["nome_curto"] or c["numero_instrumento"],
                       "orgao_id": c["orgao_id"], "saldo_centavos": saldo,
                       "execucao_fim": v.get("execucao_fim_vigente"), "dias": (fim - hoje).days if fim else None})
    saldo = sum(x["saldo_centavos"] for x in linhas)
    ritmo_mes = int((Decimal(ritmo) / 6).quantize(Decimal("1"), rounding=ROUND_HALF_UP))  # arredondamento unico
    nomes = {r["id"]: r["nome"] for r in conn.execute("SELECT id, nome FROM orgaos")}
    por_orgao: dict = {}
    for x in linhas:
        nome = nomes.get(x["orgao_id"], "sem órgão")
        por_orgao[nome] = por_orgao.get(nome, 0) + x["saldo_centavos"]
    return {"saldo_centavos": saldo, "ritmo_mensal_centavos": ritmo_mes,
            "meses_de_producao": round(saldo / ritmo_mes, 1) if ritmo_mes > 0 else None,
            "por_orgao": [{"orgao": k, "saldo_centavos": v, "fracao": v / saldo if saldo else 0}
                          for k, v in sorted(por_orgao.items(), key=lambda kv: -kv[1])]}


def _obras(conn, hoje: datetime.date, avisos: list[dict]) -> list[dict]:
    por_obra: dict = {}
    for a in avisos:
        if a.get("contrato_id"):
            por_obra.setdefault(a["contrato_id"], []).append(a)
    out = []
    for linha in qdop.linhas(conn, hoje):
        av = por_obra.get(linha["contrato_id"], [])
        farol = "vermelho" if any(a["nivel"] == "critico" for a in av) else "amarelo" if av else "verde"
        # A5 (mapa de 2026-09-28; backlog de 2026-09-25): os motivos um a um, na ordem dos avisos (nivel e
        # dias), sem o prefixo com o nome da obra, que a linha ja' mostra. `motivo` fica para o QDOP exportado.
        prefixo = f"{av[0]['obra']}: " if av and av[0].get("obra") else None
        motivos = [{"tipo": a["tipo"], "nivel": a["nivel"], "dias": a["dias"], "valor_centavos": a["valor_centavos"],
                    "texto": a["mensagem"][len(prefixo):] if prefixo and a["mensagem"].startswith(prefixo) else a["mensagem"]}
                   for a in av]
        out.append({**linha, "farol": farol, "motivo": "; ".join(a["mensagem"] for a in av), "motivos": motivos})
    return out


def da_obra(conn, contrato_id: int) -> dict:
    """Faturado e a receber de UMA obra, em valor CHEIO (a pagina da obra mostra o contrato inteiro; mapa de
    2026-09-28, mudanca A3). As regras sao as desta tela e do QDOP: faturado = medicoes com nota emitida,
    protocoladas, com NF do legado ou recebidas, no atestado quando houver; a receber = protocoladas e com NF
    do legado, mais as cobrancas do RM em aberto da obra (`_notas_em_aberto`). O a receber so' tem valor com o
    total liberado, como o protocolado desta tela."""
    faturado = conn.execute(
        "SELECT COALESCE(SUM(COALESCE(valor_atestado_centavos, valor_protocolado_centavos)), 0) FROM medicoes "
        "WHERE contrato_id=? AND estado IN ('nota_emitida','protocolada','nf_emitida','recebida')", (contrato_id,)).fetchone()[0]
    a_receber = None
    if _liberado(conn):
        cheio = lambda m: m["valor_atestado_centavos"] if m["valor_atestado_centavos"] is not None else m["valor_protocolado_centavos"] or 0
        ms = [m for m in _medicoes(conn) if m["contrato_id"] == contrato_id and m["estado"] in PROTOCOLADAS]
        a_receber = sum(cheio(m) for m in ms) + sum(cheio(n) for n in _notas_em_aberto(conn) if n["contrato_id"] == contrato_id)
    return {"faturado_centavos": faturado, "a_receber_centavos": a_receber}


def _obras_base(conn) -> dict:
    """A-21 (10/10/2026): de que sao feitas as obras do farol (o QDOP conta tudo que nao e' rescindido), para a
    tela dizer a base; "ativas" e' a definicao unica de `avisos.ativos` (ativo sem encerramento iniciado)."""
    base = {"ativas": 0, "encerramento": 0, "suspensas": 0, "encerradas": 0}
    for c in conn.execute("SELECT c.estado, c.encerramento_iniciado_em FROM contratos c "
                          "JOIN orgaos o ON o.id=c.orgao_id WHERE c.estado<>'rescindido'"):   # o filtro de qdop.linhas
        chave = ("suspensas" if c["estado"] == "suspenso" else "encerradas" if c["estado"] == "encerrado"
                 else "encerramento" if c["encerramento_iniciado_em"] else "ativas")
        base[chave] += 1
    return base


def painel(conn, hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    liberado = _liberado(conn)
    ms = _medicoes(conn)
    notas = _notas_em_aberto(conn) if liberado else []
    cache: dict = {}
    avisos = _av.listar(conn, hoje, publico="diretoria")
    return {"hoje": hoje.isoformat(), "total_a_receber_liberado": liberado,
            "dinheiro": _dinheiro(conn, ms, hoje, liberado, notas), "mes_ano": _mes_ano(conn, ms, hoje, cache),
            "proximos": _proximos(conn, ms, hoje, liberado, cache, notas), "carteira": _carteira(conn, ms, hoje),
            "obras": _obras(conn, hoje, avisos), "obras_base": _obras_base(conn), "avisos": avisos}


def avisos_pagamento(conn, hoje: datetime.date | None = None) -> list[dict]:
    """Medicao protocolada ha mais dias que o prazo normal do orgao (so' para a diretoria).

    So' com o total a receber liberado: antes da conciliacao com a controladoria o historico carregado tem
    ~420 medicoes "protocoladas" que nunca foram marcadas como recebidas (sem nota ligada), e o aviso
    acusaria atraso em pagamento que ja' entrou."""
    hoje = hoje or tempo.hoje_local()
    liberado = _liberado(conn)
    if not liberado:
        return []
    ms = _medicoes(conn)
    prazos_q3: dict = {}
    out = []
    notas = [n for n in _notas_em_aberto(conn) if _cota(n) >= AVISO_NOTA_MINIMO]
    for m in [*ms, *notas]:
        if m["estado"] not in PROTOCOLADAS or m["contrato_estado"] == "encerrado" or not _d(m["protocolo_em"]):
            continue
        if m["orgao_id"] not in prazos_q3:
            prazos_q3[m["orgao_id"]] = _prazo(ms, m["orgao_id"], hoje, QUARTIL)
        dias, prazo = (hoje - _d(m["protocolo_em"])).days, prazos_q3[m["orgao_id"]]
        if dias > prazo:
            if m["tipo"] == "nota":
                texto = f"NF {m['nf']} emitida há {dias} dias sem pagamento no RM"
            else:
                titulo = f"Reajuste da {m['numero']}ª Medição" if m["tipo"] == "reajuste" else f"{m['numero']}ª Medição"
                texto = f"{titulo} protocolada há {dias} dias"
            # A12 (2026-09-28): a medicao, para o aviso levar ao recebimento dela; a nota do RM nao tem medicao
            out.append({**_av.aviso("pagamento_atrasado", "acao",
                                    f"{texto}; o prazo normal do órgão é {prazo} dias",
                                    m["contrato_id"], m["obra"], dias=dias, valor_centavos=_cota(m) if liberado else None,
                                    publico=("diretoria",), data=_d(m["protocolo_em"]).isoformat(), sentido="desde"),
                        "medicao_id": None if m["tipo"] == "nota" else m["id"]})
    return out
