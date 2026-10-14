"""F03b — V-01/V-12/V-02 usando um espelho GERADO agora (o .docx existe em disco; o dev não tem os anexos antigos).

Gera um espelho num contrato com regra ativa, depois:
- V-01a: envia 2x em sequência (espelho não tem trava) → espera 2 e-mails;
- V-01b: envia 3x em paralelo (corrida, sem checagem) → espera vários e-mails;
- V-12/Cco: confere no simulado que para externo e Cco livres foram aceitos;
- V-02: trava o banco e envia 1x → se 5xx mas o simulado ganhou arquivo e `envios` não, falha existe.
Cada e-mail é SIMULADO (@exemplo.com). Conta o correio antes/depois.
"""
import json
import pathlib
import sqlite3
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comum import CORREIO, DB, Cliente, Registro, conferir_simulador, contar_correio, db_ro, resumo

reg = Registro("f03b")
CONTRATO = 8  # MT-402, sinfra-suef1, regra ativa, entradas {medicao, reajuste}


def gerar_espelho(eng, numero, competencia="2026-10"):
    corpo = {"numero": numero, "competencia": competencia,
             "entradas": {"medicao": "1.000,00", "reajuste": "0,00"}}
    r = eng.post(f"/api/contratos/{CONTRATO}/espelho", json=corpo)
    return r


def ultimo_simulado():
    arqs = sorted(CORREIO.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return json.loads(arqs[-1].read_text(encoding="utf-8")) if arqs else None


def main():
    conferir_simulador()
    total_antes = contar_correio()
    eng = Cliente("engenharia")

    g = gerar_espelho(eng, 901)
    if g.status_code not in (200, 201):
        reg(rota="POST /api/contratos/{id}/espelho", caso="gerar espelho base", obtido=resumo(g), flag="PULOU")
        print("nao consegui gerar espelho:", resumo(g))
        return
    eid = g.json().get("espelho_id")
    reg(rota="POST /api/contratos/{id}/espelho", caso=f"gerar espelho base numero 901 (contrato {CONTRATO})",
        obtido=resumo(g), nota=f"espelho_id={eid}")

    pv = eng.get(f"/api/espelhos/{eid}/envio")
    try:
        para = [p for p in (pv.json().get("para") or []) if "@" in p][:1]
    except Exception:
        para = []
    para = para or ["faturamento@exemplo.com"]
    base = {"para": ["destino-externo-fuzz@exemplo.com"], "copia": [],
            "cco": ["oculto-fuzz@exemplo.com"], "assunto": "fuzz V-01 espelho gerado (simulado)",
            "corpo": "teste de quebra - simulado, nao enviar de verdade"}

    # V-01a: 2x em sequência
    a0 = contar_correio()
    r1 = eng.post(f"/api/espelhos/{eid}/enviar", json=base)
    r2 = eng.post(f"/api/espelhos/{eid}/enviar", json=base)
    a1 = contar_correio()
    reg(rota="POST /api/espelhos/{id}/enviar", caso=f"V-01a espelho {eid} 2x em sequencia",
        esperado="2o recusado (sem trava)", obtido=f"{r1.status_code}/{r2.status_code} correio +{a1-a0}",
        flag="FUGIU" if r1.status_code == 200 and r2.status_code == 200 else "")

    # V-12/Cco no simulado
    sim = ultimo_simulado()
    if sim:
        reg(rota="correio-simulado (espelho)", caso="V-12 destinatario livre + Cco",
            esperado="destinatario validado; Cco consciente",
            obtido=f"para={sim.get('para')} cco={sim.get('cco')} remetente={sim.get('remetente')}",
            flag="FUGIU" if sim.get("para") == ["destino-externo-fuzz@exemplo.com"] else "")

    # V-01b: 3x em paralelo (corrida)
    res = []
    b0 = contar_correio()

    def f():
        res.append(eng.post(f"/api/espelhos/{eid}/enviar", json=base))
    ts = [threading.Thread(target=f) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    b1 = contar_correio()
    cods = [r.status_code for r in res]
    reg(rota="POST /api/espelhos/{id}/enviar", caso=f"V-01b espelho {eid} 3x em paralelo (corrida)",
        esperado="no maximo 1 envio", obtido=f"cods={cods} correio +{b1-b0}",
        flag="FUGIU" if cods.count(200) > 1 else "")

    # V-02: lock do banco durante um envio
    estado = {}

    def segura():
        c = sqlite3.connect(DB.as_posix(), timeout=1)
        try:
            c.execute("BEGIN IMMEDIATE")
            estado["lock"] = "pego"
            time.sleep(8)
            c.rollback()
        except Exception as e:
            estado["lock"] = f"falhou: {e}"
        finally:
            c.close()

    n0 = db_ro().execute("SELECT COUNT(*) FROM envios").fetchone()[0]
    c0 = contar_correio()
    t = threading.Thread(target=segura)
    t.start()
    time.sleep(0.4)
    r = eng.post(f"/api/espelhos/{eid}/enviar", json=base, timeout=30)
    t.join()
    c1 = contar_correio()
    with db_ro() as c:
        n1 = c.execute("SELECT COUNT(*) FROM envios").fetchone()[0]
    enviou_sem_registrar = (c1 - c0) >= 1 and n1 == n0 and r.status_code >= 500
    reg(rota="POST /api/espelhos/{id}/enviar", caso=f"V-02 lock durante envio (espelho {eid})",
        esperado="ou nao envia, ou envia E registra",
        obtido=f"lock={estado.get('lock')} cod={r.status_code} correio +{c1-c0} envios {n0}->{n1} resp={r.text[:60]}",
        flag="FUGIU" if enviou_sem_registrar else "")

    total_depois = contar_correio()
    print(f"CORREIO SIMULADO total: antes={total_antes} depois={total_depois} (+{total_depois-total_antes})")


if __name__ == "__main__":
    main()
