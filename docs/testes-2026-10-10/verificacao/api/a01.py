import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-01: 3 POST simultaneos de envio do MESMO espelho (MT-401, novo) geram e-mails duplicados?
import threading
s = Sessao("engenharia")
for rod, numero in ((1, 33), (2, 34)):
    titulo(f"A-01 rodada {rod}: espelho MT-401 nº {numero}")
    r = s.post("/api/contratos/5/espelho", json={"numero": numero, "competencia": "2026-10", "entradas": {"medicao": "100,00"}})
    print("gerar espelho:", resumo(r, 200)); eid = r.json()["espelho_id"]
    prev = s.get(f"/api/espelhos/{eid}/envio").json()
    print("previa: para=", prev["para"], "copia=", prev["copia"], "assunto=", prev["assunto"][:80], "| avisos=", prev["avisos"])
    corpo = {"para": prev["para"], "copia": prev["copia"], "cco": [], "assunto": prev["assunto"], "corpo": prev["corpo"]}
    antes = n_enviados(); env_antes = sql("select count(*) n from envios where tipo='espelho'")[0]["n"]
    out = []
    def dispara():
        rr = httpx.Client(base_url=BASE, timeout=120, cookies=s.cli.cookies, headers={"X-CSRF-Token": s.csrf}).post(f"/api/espelhos/{eid}/enviar", json=corpo)
        out.append((rr.status_code, rr.text[:120]))
    ts = [threading.Thread(target=dispara) for _ in range(3)]
    [t.start() for t in ts]; [t.join() for t in ts]
    print("respostas:", out)
    depois = n_enviados(); env_depois = sql("select count(*) n from envios where tipo='espelho'")[0]["n"]
    print(f"simulador: {antes} -> {depois} (+{depois-antes}) | envios tipo=espelho no banco: {env_antes} -> {env_depois} (+{env_depois-env_antes})")
    print("envio_medicoes do espelho:", sql("select em.envio_id, em.medicao_id from envio_medicoes em join espelho_medicoes x on x.medicao_id=em.medicao_id where x.espelho_id=?", eid))
    print("medicoes do espelho:", sql("select m.id, m.estado from medicoes m join espelho_medicoes x on x.medicao_id=m.id where x.espelho_id=?", eid))
    for p in enviados()[antes:]:
        j = ler_enviado(p); print("  ", os.path.basename(p), "remetente=", j["remetente"], "para=", j["para"], "cco=", j["cco"], "assunto=", j["assunto"][:60])
