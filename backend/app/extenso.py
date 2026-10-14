"""Valor por extenso em reais, regra do motor antigo do espelho (levantamento 2026-09-22 §3).

Entrada em CENTAVOS inteiros (nada de float). Saida em minusculas com acento; o espelho
imprime em caixa alta. Diferencas de grafia ("três", "quatorze", "cinquenta", "milhão") sao
exatamente o que o gabarito pega.
"""
_UNIDADES = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze",
             "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
             "oitocentos", "novecentos"]


def _tres(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "cem"
    partes = []
    if n >= 100:
        partes.append(_CENTENAS[n // 100])
    resto = n % 100
    if 0 < resto < 20:
        partes.append(_UNIDADES[resto])
    elif resto >= 20:
        d, u = divmod(resto, 10)
        partes.append(_DEZENAS[d] + (f" e {_UNIDADES[u]}" if u else ""))
    return " e ".join(partes)


def inteiro(n: int) -> str:
    if n == 0:
        return "zero"
    if n >= 1_000_000_000:
        raise ValueError("valor acima de 999 milhões não tem extenso definido")
    mi, resto = divmod(n, 1_000_000)
    mil, uni = divmod(resto, 1000)
    grupos = []   # (texto, valor bruto do grupo)
    if mi:
        grupos.append((_tres(mi) + (" milhão" if mi == 1 else " milhões"), mi))
    if mil:
        grupos.append(("mil" if mil == 1 else _tres(mil) + " mil", mil))
    if uni:
        grupos.append((_tres(uni), uni))
    texto = grupos[0][0]
    for i, (t, bruto) in enumerate(grupos[1:], start=1):
        ultimo = i == len(grupos) - 1
        sep = " e " if ultimo and (bruto < 100 or bruto % 100 == 0) else ", "
        texto += sep + t
    return texto


def reais(centavos: int) -> str:
    if centavos < 0:
        raise ValueError("valor negativo não tem extenso")
    r, c = divmod(int(centavos), 100)
    partes = []
    if r:
        de = " de" if r % 1_000_000 == 0 else ""
        partes.append(inteiro(r) + de + (" real" if r == 1 else " reais"))
    if c:
        partes.append(inteiro(c) + (" centavo" if c == 1 else " centavos"))
    return " e ".join(partes) if partes else "zero reais"
