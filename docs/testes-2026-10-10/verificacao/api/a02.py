import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-02: 3 POST simultaneos de envio do MESMO protocolo de nota (3) duplicam o e-mail? (banco restaurado antes)
import threading
rod = sys.argv[1] if len(sys.argv) > 1 else "?"
s = Sessao("engenharia", timeout=120)
titulo(f"A-02 rodada {rod}")
d = s.get("/api/notas/envio/3").json(); prev = d["previa"] if "previa" in d else d
print("chaves do detalhe:", list(d.keys()))
print("previa: para=", prev.get("para"), "copia=", prev.get("copia"), "| pendencias=", d.get("pendencias"), "| situacao protocolo=", d.get("protocolo", {}).get("situacao") if isinstance(d.get("protocolo"), dict) else d.get("situacao"))
corpo = {"para": prev["para"], "copia": prev["copia"], "assunto": prev["assunto"], "corpo": prev["corpo"],
         "justificativa": "verificacao A-02: envio com pendencias para teste de concorrencia"}
antes = n_enviados(); env_antes = sql("select count(*) n from envios where tipo='protocolo'")[0]["n"]
mp_antes = sql("select count(*) n from medicao_protocolos where medicao_id=631")[0]["n"]
out = []
def dispara():
    rr = httpx.Client(base_url=BASE, timeout=120, cookies=s.cli.cookies, headers={"X-CSRF-Token": s.csrf}).post("/api/notas/envio/3/enviar", json=corpo)
    out.append((rr.status_code, rr.text[:140]))
ts = [threading.Thread(target=dispara) for _ in range(3)]
[t.start() for t in ts]; [t.join() for t in ts]
print("respostas:", out)
depois = n_enviados(); env_depois = sql("select count(*) n from envios where tipo='protocolo'")[0]["n"]
mp_depois = sql("select count(*) n from medicao_protocolos where medicao_id=631")[0]["n"]
print(f"simulador: {antes} -> {depois} (+{depois-antes}) | envios tipo=protocolo: {env_antes} -> {env_depois} (+{env_depois-env_antes}) | medicao_protocolos da 631: {mp_antes} -> {mp_depois}")
print("protocolo 3:", sql("select id, situacao, envio_id from protocolos where id=3"))
print("medicao 631:", sql("select id, estado, congelada from medicoes where id=631"))
for p in enviados()[antes:]:
    j = ler_enviado(p); print("  ", os.path.basename(p), "para=", j["para"], "assunto=", j["assunto"][:70], "anexos=", len(j["anexos"]))
