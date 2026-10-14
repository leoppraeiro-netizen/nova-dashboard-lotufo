import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-19: certidao manual (PDF em branco) com validade 2099 vira a vigente
PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\nxref\n0 4\n0000000000 65535 f \n"
       b"0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n")
s = Sessao("engenharia", timeout=180)
ents = s.get("/api/entidades").json()
lot = next(e for e in ents if e.get("papel") == "lotufo")
print("Lotufo:", lot["id"], lot["nome"])
def municipal_lotufo():
    return sql("select c.id, c.emissao, c.validade, c.estado, c.leitura from certidoes c join certidao_tipos t on t.id=c.tipo_id "
               "where c.entidade_id=? and t.chave='municipal' order by c.id desc limit 3", lot["id"])
for rod in (1, 2):
    titulo(f"A-19 rodada {rod}")
    t0 = time.time()
    r = s.post("/api/documentos/certidoes/ler", files={"arquivo": ("branco.pdf", PDF, "application/pdf")})
    print(f"ler ({time.time()-t0:.0f}s):", resumo(r, 300))
    print("municipal Lotufo antes:", municipal_lotufo())
    t0 = time.time()
    r = s.post("/api/documentos/certidoes",
               files={"arquivo": (f"branco{rod}.pdf", PDF + b"%" + str(rod).encode() + b"\n", "application/pdf")},
               data={"entidade_id": str(lot["id"]), "tipo": "municipal", "emissao": f"2026-10-0{rod}",
                     "validade": "2099-12-31", "natureza": "negativa", "numero": f"MANUAL-{rod}"})
    print(f"gravar ({time.time()-t0:.0f}s):", resumo(r, 400))
    print("municipal Lotufo depois:", municipal_lotufo())
    d = s.get("/api/documentos").json(); txt = json.dumps(d, ensure_ascii=False)
    i = txt.find("2099-12-31"); print("2099 em /api/documentos:", i >= 0, "| trecho:", txt[max(0, i - 450):i + 40])
