"""Numero do oficio (spec 2026-09-21 §5.4), bloco 5.

Digitado a mao, porque o contador e' da empresa inteira e vive fora do sistema. O sistema so' normaliza
("301" -> "CT-301-LT-2026") e AVISA quando o numero ja' foi usado, sem travar. Entidade sem sigla de
oficio (consorcio com carta propria, como o Integra BRT) numera "CARTA-048-2026".
"""
import re

_NUMERO = re.compile(r"(?<!\d)(\d{1,4})(?!\d)")
_ANO = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def canonico(digitado: str, sigla: str | None, ano: int) -> str:
    texto = str(digitado or "")
    anos = _ANO.findall(texto)
    m = _NUMERO.search(_ANO.sub(" ", texto))
    if m is None:
        raise ValueError("Informe o número do ofício (ex.: 301)")
    n, a = int(m.group(1)), int(anos[-1]) if anos else ano
    return f"CT-{n:03d}-{sigla}-{a}" if sigla else f"CARTA-{n:03d}-{a}"


def na_carta(canon: str) -> str:
    if canon.startswith("CARTA-"):
        _, n, a = canon.split("-")
        return f"CARTA Nº {n}/{a}"
    return canon.replace("-", "/")


def usos(conn, canon: str, ignorar: tuple[str, int] | None = None) -> list[str]:
    """Outros documentos com o mesmo numero de oficio (aviso, nao trava)."""
    out = []
    for r in conn.execute(
            "SELECT p.id, c.nome_curto, c.numero_instrumento FROM protocolos p JOIN contratos c ON c.id=p.contrato_id "
            "WHERE p.numero_oficio=? AND p.situacao<>'descartado' ORDER BY p.id", (canon,)):
        if ignorar == ("protocolo", r["id"]):
            continue
        out.append(f"protocolo {r['id']} ({r['nome_curto'] or r['numero_instrumento']})")
    for r in conn.execute(          # bloco 7: pleitos de reajuste, prazo e conclusao usam a mesma numeracao
            "SELECT p.id, p.tipo, c.nome_curto, c.numero_instrumento FROM pleitos p JOIN contratos c ON c.id=p.contrato_id "
            "WHERE p.numero_oficio=? AND p.situacao<>'descartado' ORDER BY p.id", (canon,)):
        if ignorar == ("pleito", r["id"]):
            continue
        out.append(f"pleito de {r['tipo']} {r['id']} ({r['nome_curto'] or r['numero_instrumento']})")
    return out
