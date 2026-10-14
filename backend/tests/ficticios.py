"""Identificadores FICTICIOS dos testes (issue #104): o repositorio vai ficar publico e nenhum teste pode citar
CNPJ, endereco, e-mail ou conta de empresa e de orgao reais.

Os CNPJs abaixo tem digito verificador valido (a leitura de certidao e o cadastro conferem), um por empresa, e sao
os mesmos nas fixtures (`tests/fixtures`) e nos testes. A migracao 006 semeia a entidade 1 com o CNPJ de
LOTUFO e a 032 nao semeia mais FRC (issue #110). Os testes leem o `cadastro-exemplo/`, que usa estes mesmos CNPJs.
"""

# Nas fixtures cada CNPJ aparece com a razao social ficticia da letra grega (Construtora Alfa, Engenharia Beta,
# Consorcio Gama...); aqui so' o identificador troca, o nome de cadastro (Lotufo, Guaxe...) continua o do codigo.
LOTUFO = "31200101000130"      # alfa
GUAXE = "31200202000100"       # beta
INTEGRA = "31200303000181"     # gama (consorcio)
LEBLON = "31200404000152"      # delta (consorcio)
ORIUNDI = "31200505000123"     # epsilon (consorcio)
RIVOLI = "31200606000102"      # zeta
ENCOMIND = "31200707000175"    # eta
ORGAO_A = "31300101000101"     # a secretaria estadual
ORGAO_B = "31300202000182"     # a empresa estadual de participacoes
ORGAO_C = "31300303000153"     # a prefeitura

# CNPJ por chave de entidade do cadastro
ENTIDADES = {"lotufo": LOTUFO, "guaxe": GUAXE, "integra-brt": INTEGRA, "complexo-leblon": LEBLON,
             "oriundi": ORIUNDI, "rivoli": RIVOLI, "encomind": ENCOMIND,
             "via-parecis": "31200808000146", "br-163": "31200909000117", "montante": "31201010000119"}
# CNPJ por chave de orgao (prefixo da chave)
ORGAOS = {"sinfra": ORGAO_A, "mtpar": ORGAO_B, "pref-cuiaba": ORGAO_C}


def mascara(cnpj: str) -> str:
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

