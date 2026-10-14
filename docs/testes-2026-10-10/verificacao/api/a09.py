import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-09: protocolar a medicao 591 (prevista) pela rota manual, como engenharia, pulando nota e envio
s = Sessao("engenharia")
titulo("A-09 rodada 1 (medicao 591)")
print("antes:", s.get("/api/medicoes/591").json()["estado"])
r = s.post("/api/medicoes/591/protocolo", json={"data": "2026-10-10", "numero_oficio": "OF-A09"})
print("sem justificativa:", resumo(r, 300))
if r.status_code != 201:
    r = s.post("/api/medicoes/591/protocolo", json={"data": "2026-10-10", "numero_oficio": "OF-A09",
                                                    "apesar_das_pendencias": True, "justificativa": "verificacao A-09"})
    print("apesar das pendencias:", resumo(r, 300))
print("depois:", s.get("/api/medicoes/591").json()["estado"])
titulo("A-09 rodada 2 (outra medicao prevista do mesmo contrato)")
outras = sql("select id, numero, tipo, estado from medicoes where contrato_id=17 and estado='prevista' and id<>591 order by id limit 3")
print(outras)
if outras:
    mid = outras[0]["id"]
    r = s.post(f"/api/medicoes/{mid}/protocolo", json={"data": "2026-10-10", "numero_oficio": "OF-A09b",
                                                       "apesar_das_pendencias": True, "justificativa": "verificacao A-09"})
    print(mid, "->", resumo(r, 200), "| estado:", s.get(f"/api/medicoes/{mid}").json()["estado"])
