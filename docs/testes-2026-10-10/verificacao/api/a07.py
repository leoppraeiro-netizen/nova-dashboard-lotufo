import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-07: id gigante derruba rotas com 500?
s = Sessao("engenharia")
for rod in (1, 2):
    titulo(f"A-07 rodada {rod}")
    for url in ("/api/medicoes/9223372036854775808", "/api/contratos/99999999999999999999",
                "/api/medicoes/9223372036854775807", "/api/contratos/9223372036854775807",
                "/api/espelhos/9223372036854775808", "/api/protocolos/99999999999999999999"):
        r = s.get(url); print(url, "->", resumo(r, 160))
