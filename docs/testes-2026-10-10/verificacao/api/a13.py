import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-13: link 'do OneDrive' de qualquer dominio e' aceito e entra no e-mail (protocolo 3)
s = Sessao("engenharia")
for rod in (1, 2):
    titulo(f"A-13 rodada {rod}")
    url = f"https://exemplo-malicioso.test/x{rod}"
    r = s.post("/api/protocolos/3/links", json={"nome": "Planilha", "url": url})
    print("POST links:", r.status_code, json.dumps(r.json().get("links") if r.status_code == 200 else r.text, ensure_ascii=False)[:300])
    d = s.get("/api/notas/envio/3").json()
    txt = json.dumps(d, ensure_ascii=False)
    print("url na previa do envio:", url in txt)
    i = txt.find(url); print("trecho:", txt[max(0, i - 220):i + 60])
