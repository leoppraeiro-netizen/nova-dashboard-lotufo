import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-03: com o banco travado (BEGIN IMMEDIATE ~8 s em outra conexao), o e-mail sai, o envio nao e' registrado
# e a resposta manda repetir? (espelho novo do MT-401)
import sqlite3, threading
s = Sessao("engenharia", timeout=120)   # login ANTES do lock (login grava sessao)
for rod, numero in ((1, 35), (2, 36)):
    titulo(f"A-03 rodada {rod}: espelho MT-401 nº {numero}")
    r = s.post("/api/contratos/5/espelho", json={"numero": numero, "competencia": "2026-10", "entradas": {"medicao": "100,00"}})
    eid = r.json()["espelho_id"]; prev = s.get(f"/api/espelhos/{eid}/envio").json()
    corpo = {"para": ["destino@exemplo.com"], "copia": [], "cco": [], "assunto": prev["assunto"], "corpo": prev["corpo"]}
    antes = n_enviados(); env_antes = sql("select count(*) n from envios")[0]["n"]
    pronto = threading.Event()
    def trava():
        c = sqlite3.connect(DB, timeout=10); c.execute("BEGIN IMMEDIATE"); c.execute("update usuarios set nome=nome where id=7")
        pronto.set(); time.sleep(8); c.rollback(); c.close()
    t = threading.Thread(target=trava); t.start(); pronto.wait()
    t0 = time.time(); rr = s.post(f"/api/espelhos/{eid}/enviar", json=corpo); dt = time.time() - t0
    print(f"POST enviar durante o lock ({dt:.1f}s):", rr.status_code, rr.headers.get("Retry-After"), rr.text[:160])
    t.join()
    depois = n_enviados(); env_depois = sql("select count(*) n from envios")[0]["n"]
    print(f"simulador: {antes} -> {depois} (+{depois-antes}) | tabela envios: {env_antes} -> {env_depois} (+{env_depois-env_antes})")
    print("espelho envio_id:", sql("select id, envio_id, situacao from espelhos where id=?", eid),
          "| medicao:", sql("select m.id, m.estado from medicoes m join espelho_medicoes x on x.medicao_id=m.id where x.espelho_id=?", eid))
    for p in enviados()[antes:]:
        j = ler_enviado(p); print("  arquivo", os.path.basename(p), "para=", j["para"], "assunto=", j["assunto"][:60])
