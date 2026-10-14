import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-14: valor com algarismo arabico-indico aceito no atestado (medicao 591)
s = Sessao("engenharia")
ARABE = "١٢٣,٤٥"  # ١٢٣,٤٥
for rod, data in ((1, "2026-10-01"), (2, "2026-10-02")):
    titulo(f"A-14 rodada {rod}")
    r = s.put("/api/medicoes/591/valor", json={"campo": "atestado", "valor": ARABE, "data": data})
    print("PUT valor=", ARABE, "->", resumo(r, 200))
    m = s.get("/api/medicoes/591").json()
    print("atestado agora:", m["valor_atestado_centavos"], m["valor_atestado_origem"], m["atestado_em"])
