import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-15: numero do orgao em branco apaga o ja gravado (medicao 635, protocolada, MTPAR)
s = Sessao("engenharia")
def numero():
    for l in s.get("/api/notas/aguardando-pagamento").json():
        if l.get("medicao_id") == 635 or l.get("id") == 635:
            return {k: v for k, v in l.items() if "numero" in k or "orgao" in k}
    return "635 nao esta na lista"
def banco():
    return (sql("select p.id, p.numero_orgao from protocolos p join protocolo_medicoes pm on pm.protocolo_id=p.id where pm.medicao_id=635 and p.situacao='enviado'"),
            sql("select id, numero_processo from medicao_protocolos where medicao_id=635"))
for rod in (1, 2):
    titulo(f"A-15 rodada {rod}")
    print("antes:", numero(), banco())
    print(f"grava X-{rod}:", resumo(s.post("/api/notas/635/numero-orgao", json={"numero": f"X-{rod}"}), 120))
    print("depois de gravar:", numero(), banco())
    print("grava '':", resumo(s.post("/api/notas/635/numero-orgao", json={"numero": ""}), 120))
    print("depois de vazio:", numero(), banco())
