import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-21: 'obras ativas' em tres rotas x banco
s = Sessao("engenharia")
for rod in (1, 2):
    titulo(f"A-21 rodada {rod}")
    res = s.get("/api/medicoes/resumo").json(); pai = s.get("/api/inicio/painel").json(); dire = s.get("/api/diretoria").json()
    print("/api/medicoes/resumo -> len(obras) =", len(res["obras"]), "(contratos estado='ativo')")
    print("/api/inicio/painel -> protocoladas =", pai["protocoladas"])
    print("/api/diretoria -> len(obras) (farol) =", len(dire["obras"]), "| estados no farol:", sorted({(o.get("situacao") or o.get("estado") or "?") for o in dire["obras"]}))
    print("  1a linha do farol:", json.dumps({k: dire["obras"][0][k] for k in list(dire["obras"][0])[:8]}, ensure_ascii=False))
    print("banco: contratos por estado =", sql("select estado, count(*) n from contratos group by estado"),
          "| ativo sem encerramento =", sql("select count(*) n from contratos where estado='ativo' and encerramento_iniciado_em is null")[0]["n"],
          "| <> rescindido =", sql("select count(*) n from contratos where estado<>'rescindido'")[0]["n"])
