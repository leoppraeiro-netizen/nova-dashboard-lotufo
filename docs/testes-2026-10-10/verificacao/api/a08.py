import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-08: nota manual com valor gigante -> 500? (medicao 640, documento nfs 210)
s = Sessao("engenharia")
for rod in (1, 2):
    titulo(f"A-08 rodada {rod}")
    r = s.post("/api/medicoes/640/notas/manual",
               json={"documento_id": 210, "numero": 123, "emissao": "2026-10-01", "valor": "99999999999999999999,00"})
    print("20 digitos:", resumo(r, 300))
    r = s.post("/api/medicoes/640/notas/manual",
               json={"documento_id": 210, "numero": 123, "emissao": "2026-10-01", "valor": "9999999999999999,00"})
    print("controle 16 digitos (999.999.999.999.999.900 centavos, cabe em int64):", resumo(r, 200))
