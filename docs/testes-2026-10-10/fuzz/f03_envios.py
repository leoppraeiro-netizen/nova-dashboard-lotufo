"""F03 — sondas que disparam e-mail (só com o simulador): V-01 (corrida), V-02 (enviado e não registrado),
V-12 (destinatário/Cco livres) e S5 (Cco descartado no envio da nota). S10 (link https qualquer) não envia.

Todo destinatário é @exemplo.com / @lotufo.com. Conta o correio simulado antes/depois de cada bloco.
"""
import pathlib
import sqlite3
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comum import BASE, DB, Cliente, Registro, conferir_simulador, contar_correio, db_ro, resumo

reg = Registro("f03")


def s10_link_dominio(eng):
    """Link de OneDrive aceita qualquer domínio https (vai clicável ao órgão). Não envia e-mail."""
    pid = 3  # protocolo rascunho (contrato 20, nota)
    for _ in range(2):
        rr = eng.post(f"/api/protocolos/{pid}/links",
                      json={"nome": "Documento juntado - fuzz", "url": "https://exemplo-malicioso.test/arquivo-fuzz"})
        reg(rota="POST /api/protocolos/{pid}/links", caso=f"S10 dominio https arbitrario (pid {pid})",
            esperado="idealmente só sharepoint/onedrive", obtido=resumo(rr),
            flag="FUGIU" if rr.status_code == 200 else "")


def v01_espelho(eng):
    """Espelho não tem trava de reenvio: 2 POSTs seguidos = 2 e-mails."""
    with db_ro() as c:
        esp = c.execute("SELECT id FROM espelhos WHERE situacao='vigente' AND envio_id IS NULL ORDER BY id LIMIT 1").fetchone()
    if not esp:
        reg(rota="POST /api/espelhos/{id}/enviar", caso="V-01 espelho", obtido="sem espelho elegível", flag="PULOU")
        return
    eid = esp[0]
    pv = eng.get(f"/api/espelhos/{eid}/envio")
    try:
        para = pv.json().get("para") or []
    except Exception:
        para = []
    para = [p for p in para if "@" in p][:1] or ["faturamento@exemplo.com"]
    corpo = {"para": para, "copia": [], "cco": [], "assunto": "fuzz V-01 espelho (simulado)",
             "corpo": "teste de corrida - nao enviar de verdade"}
    antes = contar_correio()
    r1 = eng.post(f"/api/espelhos/{eid}/enviar", json=corpo)
    r2 = eng.post(f"/api/espelhos/{eid}/enviar", json=corpo)
    depois = contar_correio()
    dois = r1.status_code == 200 and r2.status_code == 200
    reg(rota="POST /api/espelhos/{id}/enviar", caso=f"V-01 espelho {eid} 2x seguidos",
        esperado="2o recusado (sem trava)", obtido=f"{r1.status_code}/{r2.status_code} correio +{depois-antes}",
        flag="FUGIU" if dois else "")


def v01_nota_corrida(eng):
    """3 POSTs paralelos de envio da nota passam a mesma checagem 'já enviado?' → múltiplos e-mails."""
    with db_ro() as c:
        m = c.execute("SELECT id, contrato_id FROM medicoes WHERE estado='nota_emitida' ORDER BY id LIMIT 1").fetchone()
    if not m:
        reg(rota="POST /api/notas/envio/{pid}/enviar", caso="V-01 nota", obtido="sem nota_emitida", flag="PULOU")
        return None
    mid, cid = m
    ini = eng.post("/api/notas/envio/iniciar", json={"contrato_id": cid, "medicao_ids": [mid],
                                                     "numero_oficio": "CT-999-LT-2026"})
    if ini.status_code != 200:
        reg(rota="POST /api/notas/envio/iniciar", caso=f"V-01 iniciar med={mid} contr={cid}",
            obtido=resumo(ini), flag="PULOU")
        return None
    pid = ini.json()["protocolo_id"]
    pv = eng.get(f"/api/notas/envio/{pid}")
    try:
        d = pv.json()
        para = [p for p in (d.get("previa", {}).get("para") or d.get("para") or []) if "@" in p][:1]
    except Exception:
        para = []
    para = para or ["orgao-externo@exemplo.com"]
    # V-12: destinatário externo livre; S5: Cco enviado via JSON deve ser ignorado pela API (modelo não tem cco)
    corpo = {"para": para, "copia": [], "cco": ["oculto-fuzz@exemplo.com"],
             "assunto": "fuzz V-01 nota (simulado)", "corpo": "teste de corrida - nao enviar de verdade",
             "justificativa": "teste de quebra - pendencias ignoradas de proposito nesta medicao de teste"}
    res = []
    antes = contar_correio()

    def f():
        res.append(eng.post(f"/api/notas/envio/{pid}/enviar", json=corpo))
    ts = [threading.Thread(target=f) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    depois = contar_correio()
    cods = [r.status_code for r in res]
    oks = cods.count(200)
    reg(rota="POST /api/notas/envio/{pid}/enviar", caso=f"V-01 nota corrida 3x (pid {pid}, med {mid})",
        esperado="1x200 e os outros 422/409", obtido=f"cods={cods} correio +{depois-antes}",
        nota="medicao vira protocolada", flag="FUGIU" if oks > 1 else "")
    return pid, para


def v12_s5_simulador(para_usado):
    """Confere no JSON simulado o destinatário livre (V-12) e se o Cco sumiu (S5)."""
    import json
    from comum import CORREIO
    arqs = sorted(CORREIO.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not arqs:
        reg(rota="correio-simulado", caso="V-12/S5", obtido="sem arquivos", flag="PULOU")
        return
    ult = json.loads(arqs[-1].read_text(encoding="utf-8"))
    cco = ult.get("cco")
    reg(rota="correio-simulado (ultimo)", caso="V-12 destinatario livre + S5 Cco",
        esperado="Cco preservado OU avisado; destinatario validado",
        obtido=f"para={ult.get('para')} copia={ult.get('copia')} cco={cco}",
        flag="FUGIU-S5" if not cco else "")


def v02_enviado_nao_registrado():
    """Trava o banco de dev com BEGIN IMMEDIATE e envia um espelho: se o 503 vier DEPOIS do e-mail sair,
    o simulador ganha arquivo mas `envios` não ganha linha e o espelho segue sem envio_id."""
    eng = Cliente("engenharia")
    with db_ro() as c:
        esp = c.execute("SELECT id FROM espelhos WHERE situacao='vigente' AND envio_id IS NULL ORDER BY id LIMIT 1").fetchone()
    if not esp:
        reg(rota="POST /api/espelhos/{id}/enviar", caso="V-02", obtido="sem espelho elegível", flag="PULOU")
        return
    eid = esp[0]
    pv = eng.get(f"/api/espelhos/{eid}/envio")
    try:
        para = [p for p in (pv.json().get("para") or []) if "@" in p][:1]
    except Exception:
        para = []
    para = para or ["faturamento@exemplo.com"]
    corpo = {"para": para, "copia": [], "cco": [], "assunto": "fuzz V-02 (simulado)",
             "corpo": "teste de lock - nao enviar de verdade"}

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

    n_env_antes = db_ro().execute("SELECT COUNT(*) FROM envios").fetchone()[0]
    antes = contar_correio()
    t = threading.Thread(target=segura)
    t.start()
    time.sleep(0.4)
    r = eng.post(f"/api/espelhos/{eid}/enviar", json=corpo, timeout=30)
    t.join()
    depois = contar_correio()
    with db_ro() as c:
        n_env_depois = c.execute("SELECT COUNT(*) FROM envios").fetchone()[0]
        envio_id = c.execute("SELECT envio_id FROM espelhos WHERE id=?", (eid,)).fetchone()[0]
    enviou_sem_registrar = (depois - antes) >= 1 and n_env_depois == n_env_antes and r.status_code >= 500
    reg(rota="POST /api/espelhos/{id}/enviar", caso=f"V-02 lock durante envio (espelho {eid})",
        esperado="ou não envia, ou envia E registra",
        obtido=f"lock={estado.get('lock')} cod={r.status_code} correio +{depois-antes} "
               f"envios {n_env_antes}->{n_env_depois} espelho.envio_id={envio_id} resp={r.text[:80]}",
        flag="FUGIU" if enviou_sem_registrar else "")


def main():
    conferir_simulador()
    total_antes = contar_correio()
    eng = Cliente("engenharia")
    s10_link_dominio(eng)
    v01_espelho(eng)
    saida = v01_nota_corrida(eng)
    v12_s5_simulador(saida[1] if saida else [])
    v02_enviado_nao_registrado()
    total_depois = contar_correio()
    print(f"CORREIO SIMULADO total: antes={total_antes} depois={total_depois} (+{total_depois-total_antes})")


if __name__ == "__main__":
    main()
