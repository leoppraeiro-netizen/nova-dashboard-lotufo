import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-17: Cco do envio da nota e' descartado?  A-18: na SINFRA a 631 sai sem o reajuste irmao (632) e sem aviso?
# (banco restaurado antes; um envio do protocolo 3 serve aos dois itens)
rod = sys.argv[1] if len(sys.argv) > 1 else "?"
s = Sessao("engenharia", timeout=120)
titulo(f"A-17/A-18 rodada {rod}")
d = s.get("/api/notas/envio/3").json(); prev = d["previa"] if "previa" in d else d
txt = json.dumps(d, ensure_ascii=False)
print("detalhe menciona 632 / reajuste?", "632" in txt, "reajuste" in txt.lower(), "| pendencias:", d.get("pendencias"), "| avisos:", d.get("avisos"))
ae = s.get("/api/notas/a-enviar").json()
print("a-enviar (contrato 20):", [(e["chave"], e["medicao_ids"], e["descricao"], e.get("aviso")) for e in ae["envios"] if e["contrato_id"] == 20])
print("632 antes:", sql("select id, estado from medicoes where id=632"))
antes = n_enviados()
corpo = {"para": ["orgao@exemplo.com"], "copia": [], "cco": ["oculto@exemplo.com"], "assunto": prev["assunto"], "corpo": prev["corpo"],
         "justificativa": "verificacao A-17/A-18: envio com pendencias"}
r = s.post("/api/notas/envio/3/enviar", json=corpo)
print("POST enviar com cco:", resumo(r, 300))
novos = enviados()[antes:]
for p in novos:
    j = ler_enviado(p); print("  arquivo", os.path.basename(p), "para=", j["para"], "copia=", j["copia"], "cco=", j["cco"], "| 632/reajuste no e-mail?", "632" in json.dumps(j), "reajuste" in j["corpo"].lower() or "reajuste" in j["assunto"].lower())
print("banco envios (ultimo):", sql("select id, tipo, para, copia, cco from envios order by id desc limit 1"))
print("protocolo 3:", sql("select id, situacao, envio_id, justificativa from protocolos where id=3"))
print("631 depois:", sql("select id, estado from medicoes where id=631"), "| 632 depois:", sql("select id, estado from medicoes where id=632"))
ae = s.get("/api/notas/a-enviar").json()
print("a-enviar depois (contrato 20):", [(e["chave"], e["medicao_ids"], e["descricao"], e.get("aviso")) for e in ae["envios"] if e["contrato_id"] == 20])
av = s.get("/api/inicio").json()["avisos"]
print("avisos BRT depois:", [(a.get("tipo"), a.get("mensagem")) for a in av if a.get("contrato_id") == 20])
print("auditoria do envio:", sql("select acao, depois from audit_log where acao like 'protocolo.%' order by id desc limit 2"))
