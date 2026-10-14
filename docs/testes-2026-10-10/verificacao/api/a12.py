import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-12: envio de espelho aceita destinatario e Cco externos livres (so' @exemplo.com aqui)
s = Sessao("engenharia")
eid = sql("select id from espelhos where situacao='vigente' and contrato_id=5 order by id desc limit 1")[0]["id"]
print("espelho usado:", eid)
for rod in (1, 2):
    titulo(f"A-12 rodada {rod}")
    antes = n_enviados()
    r = s.post(f"/api/espelhos/{eid}/enviar", json={"para": [f"qualquer{rod}@exemplo.com"], "copia": [], "cco": [f"oculto{rod}@exemplo.com"],
                                                 "assunto": f"Verificacao A-12 rodada {rod}", "corpo": "teste"})
    print("POST enviar:", resumo(r, 200))
    novos = enviados()[antes:]
    for p in novos:
        j = ler_enviado(p); print("  arquivo", os.path.basename(p), "para=", j["para"], "copia=", j["copia"], "cco=", j["cco"])
    print("banco envios (ultimo):", sql("select id, tipo, para, copia, cco from envios order by id desc limit 1"))
