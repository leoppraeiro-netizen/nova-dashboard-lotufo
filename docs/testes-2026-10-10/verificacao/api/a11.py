import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
# A-11: 'envio feito por fora' aceita PNG renomeado .eml (medicao em nota_emitida)
import struct, zlib, glob
def png():
    raw = b"\x00" + b"\xff\x00\x00" * 4
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
s = Sessao("engenharia")
for rod, mid in ((1, 632), (2, None)):
    titulo(f"A-11 rodada {rod}")
    if mid is None:
        cand = sql("select id from medicoes where estado='nota_emitida' and id not in (631,632) order by id desc limit 1")
        if not cand:
            print("sem outra medicao nota_emitida"); break
        mid = cand[0]["id"]
    print("medicao", mid, "antes:", s.get(f"/api/medicoes/{mid}").json()["estado"])
    r = s.post("/api/notas/envio-externo", data={"medicao_ids": str(mid), "enviado_em": "2026-10-09", "observacao": "verificacao A-11"},
               files={"eml": ("imagem.eml", png(), "message/rfc822")})
    print("POST:", resumo(r, 300))
    print("depois:", s.get(f"/api/medicoes/{mid}").json()["estado"], "| banco:", sql("select envio_origem, envio_externo_em from medicoes where id=?", mid))
    evs = sorted(glob.glob(str(RAIZ / "evidencias" / "*.eml")), key=os.path.getmtime)
    if evs:
        print("ultimo .eml gravado:", os.path.basename(evs[-1]), open(evs[-1], "rb").read(8))
