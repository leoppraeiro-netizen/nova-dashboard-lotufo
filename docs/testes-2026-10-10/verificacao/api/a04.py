import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-04: corpo de 100 MB sem login e' lido inteiro antes do 401? (o corpo grande vai uma vez so')
import time
cli = httpx.Client(base_url=BASE, timeout=600)
pequeno = json.dumps({"campo": "atestado", "valor": "1,00", "x": "A" * 900}).encode()
for i in (1, 2, 3):
    t = time.perf_counter()
    r = cli.put("/api/medicoes/631/valor", content=pequeno, headers={"Content-Type": "application/json"})
    dt_p = time.perf_counter() - t
    print(f"1 KB sem cookie ({i}):", r.status_code, r.text[:80], f"{dt_p*1000:.1f} ms")
grande = b'{"campo":"atestado","valor":"1,00","x":"' + b"A" * (100 * 1024 * 1024) + b'"}'
print("tamanho grande:", round(len(grande) / 1024 / 1024, 1), "MB")
t = time.perf_counter()
r = cli.put("/api/medicoes/631/valor", content=grande, headers={"Content-Type": "application/json"})
dt_g = time.perf_counter() - t
print("100 MB sem cookie:", r.status_code, r.text[:80], f"{dt_g:.2f} s", f"razao x{dt_g/max(dt_p,1e-6):.0f}")
# controle: 100 MB COM cookie valido (o servidor precisa ler o corpo de qualquer jeito)
s = Sessao("engenharia", timeout=600)
t = time.perf_counter()
r = s.put("/api/medicoes/631/valor", content=grande, headers={"Content-Type": "application/json"})
dt_c = time.perf_counter() - t
print("100 MB com cookie:", r.status_code, r.text[:120], f"{dt_c:.2f} s")
# rodada 2 (corpo menor, 10 MB, para nao repetir o de 100 MB): o tempo deve cair ~10x se for proporcional
medio = b'{"campo":"atestado","valor":"1,00","x":"' + b"A" * (10 * 1024 * 1024) + b'"}'
t = time.perf_counter()
r = cli.put("/api/medicoes/631/valor", content=medio, headers={"Content-Type": "application/json"})
dt_m = time.perf_counter() - t
print("10 MB sem cookie (rodada 2):", r.status_code, f"{dt_m:.3f} s", f"razao x{dt_m/max(dt_p,1e-6):.0f}")
