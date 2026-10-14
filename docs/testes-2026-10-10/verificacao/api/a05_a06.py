import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-06 (tentativas em paralelo passam do limite) e A-05 (5 erradas trancam e nao ha desbloqueio)
# na conta de diretoria (id 7); destranca por SQL no banco DESTA instancia entre rodadas.
import threading, sqlite3
email, senha = credenciais("diretoria")
def tenta(sn, out=None):
    r = httpx.Client(base_url=BASE, timeout=60).post("/api/auth/login", json={"email": email, "senha": sn})
    if out is not None: out.append(r.status_code)
    return r
def conta(): return sql("select tentativas_falhas, bloqueado_ate from usuarios where id=7")[0]
def destranca():
    c = sqlite3.connect(DB, timeout=10); c.execute("update usuarios set tentativas_falhas=0, bloqueado_ate=null where id=7"); c.commit(); c.close()
for rod in (1, 2):
    titulo(f"A-06 rodada {rod}: 10 senhas erradas em paralelo"); destranca(); print("antes:", conta())
    out = []; ts = [threading.Thread(target=tenta, args=("senha-errada-%d" % i, out)) for i in range(10)]
    [t.start() for t in ts]; [t.join() for t in ts]
    print("status das 10:", out, "| contador:", conta())
    r = tenta(senha); print("senha certa depois:", r.status_code, "->", "ENTROU" if r.status_code == 200 else "recusada")
for rod in (1, 2):
    titulo(f"A-05 rodada {rod}: 5 erradas em serie"); destranca(); print("antes:", conta())
    print("status das 5:", [tenta("errada-%d" % i).status_code for i in range(5)], "| contador:", conta())
    r = tenta(senha); print("senha certa depois:", r.status_code, "->", "ENTROU" if r.status_code == 200 else "recusada")
destranca(); print("conta 7 destrancada por SQL:", conta())
