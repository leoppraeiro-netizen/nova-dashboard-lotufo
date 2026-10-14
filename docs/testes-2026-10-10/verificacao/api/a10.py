import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-10: o texto do campo e-mail de um login falho fica na auditoria
cli = httpx.Client(base_url=BASE, timeout=30)
adm = Sessao("admin")
for rod in (1, 2):
    titulo(f"A-10 rodada {rod}")
    frase = f"minha frase secreta 123 rodada{rod}"
    r = cli.post("/api/auth/login", json={"email": frase, "senha": "qualquer-coisa"})
    print("login:", resumo(r, 120))
    ev = adm.get("/api/admin/auditoria?limite=20").json()["eventos"]
    achados = [e for e in ev if frase in json.dumps(e, ensure_ascii=False)]
    print("na auditoria:", json.dumps(achados[:1], ensure_ascii=False)[:400])
