import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-16: valor protocolado da 631 (nascida do espelho, nota_emitida) editavel depois da nota, sem aviso
s = Sessao("engenharia")
def foto():
    m = s.get("/api/medicoes/631").json()
    n = s.get("/api/medicoes/631/notas").json()
    av = s.get("/api/inicio").json()["avisos"]
    d = s.get("/api/diretoria").json()["dinheiro"]
    return {"valor": m["valor_protocolado_centavos"], "origem": m["valor_protocolado_origem"], "estado": m["estado"],
            "esperadas": [(e["chave"], e["valor"]) for e in n["esperadas"]],
            "notas": [(x["numero"], x["valor_centavos"], x["confirmacao"], x["conferencia"]) for x in n["notas"]],
            "faltam": n["faltam"],
            "avisos_total": len(av), "avisos_brt": [(a.get("tipo"), a.get("mensagem")) for a in av if a.get("contrato_id") == 20],
            "dir_nota_esperando_protocolo": d["nota_esperando_protocolo"],
            "dir_medido_esperando_nota": d["medido_esperando_nota"]}
for rod, val in ((1, "1,00"), (2, "2,00")):
    titulo(f"A-16 rodada {rod}: valor protocolado -> {val}")
    a = foto(); print("ANTES :", json.dumps(a, ensure_ascii=False))
    r = s.put("/api/medicoes/631/valor", json={"campo": "protocolado", "valor": val})
    print("PUT:", resumo(r, 200))
    d = foto(); print("DEPOIS:", json.dumps(d, ensure_ascii=False))
    print("mudou:", {k: (a[k], d[k]) for k in a if a[k] != d[k]})
    print("auditoria:", sql("select acao, antes, depois from audit_log where entidade='medicao' and entidade_id='631' order by id desc limit 1"))
