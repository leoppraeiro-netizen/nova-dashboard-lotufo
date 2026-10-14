"""Leitor deterministico das seis certidoes de protocolo (spec §9, bloco 4).

Regra de dominio portada da dashboard antiga (js/features/certidoes.js, `PERFIS`), com tres
mudancas: (1) a NATUREZA e' lida e a positiva pura e' recusada; (2) a falencia soma 30 dias uteis
descontando feriados nacionais (app/feriados.py); (3) o CNPJ escolhido e' o de uma empresa do
cadastro que aparece no documento, nao o primeiro numero com cara de CNPJ (a municipal de Cuiaba
cola a inscricao estadual no CNPJ).

Puro: texto -> campos. Nao abre PDF (`leitura_pdf.texto_de_pdf_com_limite`, em subprocesso) e nao
toca banco (`documentos.py` decide gravar). Tudo e' casado sobre `plano(texto)`: NFKC (desfaz a
ligadura "fi" e o espaco nao quebravel da certidao federal), sem acento, maiusculas, espacos
colapsados. Os valores extraidos sao digitos, datas e codigos, que a normalizacao nao altera.
"""
import datetime
import re
import unicodedata

from app import entidades, feriados

TIPOS = ("federal", "fgts", "trabalhista", "estadual", "municipal", "falencia")
NATUREZAS = ("negativa", "positiva_efeito_negativa")
MIN_TEXTO = 80
DIAS_UTEIS_FALENCIA = 30
ROTULO = {"federal": "federal", "fgts": "do FGTS", "trabalhista": "trabalhista", "estadual": "estadual",
          "municipal": "municipal", "falencia": "de falência"}
# Motivos em que a pessoa ainda pode digitar os campos (decisao 5 do plano). `positiva` e
# `empresa-desconhecida` NAO: a primeira nao serve para protocolo, a segunda nao tem a quem pertencer.
DIGITAVEIS = frozenset({"sem-texto", "tipo-desconhecido", "natureza-desconhecida", "sem-cnpj",
                        "sem-emissao", "sem-validade", "datas-incoerentes", "empresa-ambigua",
                        "datas-implausiveis"})       # gate Sol S6 (10/10/2026): prazo fora do normal do tipo
_MESES = {m: i for i, m in enumerate(("JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO", "JULHO",
                                      "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"), 1)}


class Recusa(ValueError):
    """Leitura que nao se aproveita. `motivo` e' estavel: a tela e o CLI decidem por ele."""

    def __init__(self, motivo: str, mensagem: str, lidos: dict | None = None):
        super().__init__(mensagem)
        self.motivo = motivo
        self.lidos = lidos          # o que foi lido, para pre-preencher a digitacao (S6)


def plano(texto: str) -> str:
    t = unicodedata.normalize("NFKC", texto or "")
    t = re.sub(r"(?i)certi\s+fi\s+ca", "Certifica", t)             # ligadura que o extrator separa
    t = "".join(unicodedata.normalize("NFD", c)[:1] for c in t)    # 1 para 1: tira o acento
    return re.sub(r"\s+", " ", t).upper().strip()


def sem_texto(texto: str) -> bool:
    """O mesmo corte da recusa `sem-texto` de `ler`: e' quando vale tentar o OCR."""
    return len(plano(texto)) < MIN_TEXTO


_D = r"(\d{2}/\d{2}/\d{4})"
_EXT = r"(\d{1,2}) DE ([A-Z]+) DE (\d{4})"
# Ordem da antiga: o primeiro que casar vence.
_ASSINATURAS = (
    ("falencia", re.compile(r"FALENCIA E (?:RECUPERACAO JUDICIAL|CONCORDATA)")),
    ("fgts", re.compile(r"CERTIFICADO DE REGULARIDADE DO FGTS")),
    ("trabalhista", re.compile(r"DEBITOS TRABALHISTAS")),
    ("federal", re.compile(r"TRIBUTOS FEDERAIS E A DIVIDA ATIVA DA UNIAO")),
    ("estadual", re.compile(r"GERIDOS PELA PROCURADORIA-GERAL DO ESTADO")),
    ("municipal", re.compile(r"PREFEITURA MUNICIPAL DE CUIABA")),
)
_CAMPOS = {
    "federal": {"emissao": r"DO DIA " + _D, "validade": r"VALIDA ATE:? ?" + _D,
                "numero": r"CODIGO DE CONTROLE DA CERTIDAO:? ?([0-9A-F]{4}(?:\.[0-9A-F]{4}){3})"},
    "fgts": {"faixa": r"VALIDADE:? ?" + _D + r" ?A ?" + _D, "numero": r"CERTIFICACAO NUMERO:? ?(\d{10,30})"},
    "trabalhista": {"emissao": r"EXPEDICAO:? ?" + _D, "validade": r"VALIDADE:? ?" + _D,
                    "numero": r"CERTIDAO NO:? ?(\d{5,12}/\d{4})"},
    "estadual": {"emissao": r"DATA DA EMISSAO:? ?" + _D, "validade": r"VALIDA ATE:? ?" + _D,
                 "numero": r"NUMERO DE AUTENTICACAO:? ?([A-Z0-9]{10,30})"},
    "municipal": {"emissao": r"CUIABA/MT, ?[A-Z-]+, ?" + _EXT, "validade": r"VALIDA ATE " + _EXT,
                  "numero": r"(?<![\d.])(\d{4,10}/\d{4})(?!\d)"},
    "falencia": {"emissao": r"ATE A DA[TR]A DE " + _D, "numero": r"\bNO:? ?(\d{5,12})"},
}
_POS_EFEITO = re.compile(r"POSITIVA.{0,60}?COM EFEITOS? (?:DE )?NEGATIV[OA]")
_SIGLA = re.compile(r"\b(CND|CPEND|CPD) NO\b")
# Mascarado (sem ancora a esquerda: a municipal de Cuiaba cola a inscricao estadual no CNPJ) ou os 14
# digitos soltos, sem digito nem separador colado dos dois lados (gate Sol, achado 2).
_CNPJ = re.compile(r"(\d{2})\.(\d{3})\.(\d{3})/(\d{4})-(\d{2})|(?<![\d./-])(\d{14})(?![\d./-])")
# "POSITIVA" sem "EFEITO" logo depois: certidao positiva cujo titulo o perfil nao reconheceu (gate Sol,
# achado 1) -- recusada em vez de cair na digitacao, onde a pessoa escolheria "negativa".
_POSITIVA_PURA = re.compile(r"\bPOSITIVA\b(?!.{0,60}EFEITO)")


def _natureza(tipo: str, p: str) -> str | None:
    """'negativa', 'positiva_efeito_negativa', 'positiva' ou None (nao reconhecida)."""
    if tipo == "fgts":
        return "negativa" if "ENCONTRA-SE EM SITUACAO REGULAR" in p else None
    if tipo == "falencia":
        if "NADA CONSTA" in p:
            return "negativa"
        return "positiva" if re.search(r"\bCONSTA", p) else None
    if tipo == "estadual":
        m = _SIGLA.search(p)
        if m:
            return {"CND": "negativa", "CPEND": "positiva_efeito_negativa", "CPD": "positiva"}[m.group(1)]
    if _POS_EFEITO.search(p):
        return "positiva_efeito_negativa"
    if "CERTIDAO NEGATIVA DE DEBITOS" in p:
        return "negativa"
    if "CERTIDAO POSITIVA" in p or _POSITIVA_PURA.search(p):
        return "positiva"
    return None


def _data(grupos: tuple) -> datetime.date | None:
    try:
        if len(grupos) == 1:
            d, m, a = grupos[0].split("/")
            return datetime.date(int(a), int(m), int(d))
        return datetime.date(int(grupos[2]), _MESES[grupos[1]], int(grupos[0]))
    except (ValueError, KeyError):
        return None


def cnpjs_no_texto(texto: str) -> list[str]:
    """CNPJs com DV valido que aparecem no documento, na ordem (tambem confere a empresa digitada)."""
    vistos: list[str] = []
    for m in _CNPJ.finditer(plano(texto)):
        c = "".join(g for g in m.groups() if g)
        if entidades.cnpj_valido(c) and c not in vistos:
            vistos.append(c)
    return vistos


def ler(texto: str, cnpjs_cadastrados: frozenset[str] = frozenset()) -> dict:
    p = plano(texto)
    if sem_texto(texto):
        raise Recusa("sem-texto", "O PDF não tem texto legível (foi digitalizado ou salvo como imagem) — "
                                  "informe empresa, tipo, emissão e validade.")
    tipo = next((t for t, rx in _ASSINATURAS if rx.search(p)), None)
    if tipo is None:
        raise Recusa("tipo-desconhecido", "Não reconheci a certidão (federal, FGTS, trabalhista, estadual, "
                                          "municipal de Cuiabá ou falência) — informe os campos.")
    natureza = _natureza(tipo, p)
    if natureza == "positiva":
        raise Recusa("positiva", f"A certidão {ROTULO[tipo]} é POSITIVA (há débito ou processo): não serve "
                                 f"para protocolo. Regularize e emita de novo.")
    if natureza is None:
        raise Recusa("natureza-desconhecida", f"Não achei se a certidão {ROTULO[tipo]} é negativa ou positiva "
                                              f"com efeito de negativa — informe os campos.")
    validos = cnpjs_no_texto(texto)
    do_cadastro = [c for c in validos if c in cnpjs_cadastrados]
    if len(do_cadastro) > 1:        # gate Sol, achado 3: nao escolher sozinho entre duas empresas
        raise Recusa("empresa-ambigua", "O documento cita mais de uma empresa do cadastro — escolha de qual "
                                        "é a certidão.")
    cnpj = do_cadastro[0] if do_cadastro else (validos[0] if validos else None)
    if cnpj is None:
        raise Recusa("sem-cnpj", "Não achei o CNPJ no documento — informe os campos.")

    campos, evidencia = _CAMPOS[tipo], {}

    def achar(campo):
        m = re.search(campos[campo], p)
        if m:
            evidencia[campo] = m.group(0)
        return m

    if tipo == "fgts":
        m = achar("faixa")
        emissao = _data((m.group(1),)) if m else None
        validade = _data((m.group(2),)) if m else None
    else:
        m = achar("emissao")
        emissao = _data(m.groups()) if m else None
        if tipo == "falencia":
            validade = feriados.somar_dias_uteis(emissao, DIAS_UTEIS_FALENCIA) if emissao else None
        else:
            m = achar("validade")
            validade = _data(m.groups()) if m else None
    if emissao is None:
        raise Recusa("sem-emissao", "Não achei a data de emissão — informe os campos.")
    if validade is None:
        raise Recusa("sem-validade", "Não achei a validade — informe os campos.")
    if validade <= emissao:
        raise Recusa("datas-incoerentes", "A validade lida não é posterior à emissão — informe os campos.")
    m = achar("numero")
    numero = next((g for g in m.groups() if g), None) if m else None
    return {"tipo": tipo, "natureza": natureza, "cnpj": cnpj, "emissao": emissao.isoformat(),
            "validade": validade.isoformat(), "numero": numero,
            "validade_calculada": tipo == "falencia", "evidencia": evidencia}
