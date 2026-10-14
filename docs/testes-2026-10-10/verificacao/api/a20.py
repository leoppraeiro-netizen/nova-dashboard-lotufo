import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-20: previa de espelho com competencia anterior ao contrato (MT-401, execucao desde 03/2023)
s = Sessao("engenharia")
for rod in (1, 2):
    titulo(f"A-20 rodada {rod}")
    r = s.post("/api/contratos/5/espelho/previa",
               json={"numero": 33, "competencia": "2020-01", "entradas": {"medicao": "100,00"}})
    print(resumo(r, 600))
c = s.get("/api/contratos/5").json()
print("cadastro MT-401 (datas):", json.dumps({k: v for k, v in c.items() if any(t in k for t in ("inic", "data", "assin", "fim", "termino"))}, ensure_ascii=False)[:500])
