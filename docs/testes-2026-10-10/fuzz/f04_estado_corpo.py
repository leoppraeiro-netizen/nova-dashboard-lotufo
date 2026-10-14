"""F04 — atalhos de máquina de estados (S4) e corpo hostil, sem disparar e-mail.

- S4a: protocolo manual a partir de 'prevista' (pula nota e envio);
- S4b: editar valor PROTOCOLADO de medição nascida do espelho (diverge do espelho vigente);
- S4c: cronograma por API (escrita sem tela);
- corpo: ofício 10k (>40 -> 422), emoji/HTML em motivo, tipos trocados, listas, datas absurdas.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comum import Cliente, Registro, conferir_simulador, contar_correio, db_ro, resumo

reg = Registro("f04")


def main():
    conferir_simulador()
    antes = contar_correio()
    eng = Cliente("engenharia")

    # S4a: protocolo manual a partir de 'prevista' (med 591/592 estão previstas)
    with db_ro() as c:
        prev = c.execute("SELECT id FROM medicoes WHERE estado='prevista' ORDER BY id LIMIT 1").fetchone()
    if prev:
        mid = prev[0]
        for _ in range(2):
            rr = eng.post(f"/api/medicoes/{mid}/protocolo",
                          json={"data": "2026-09-15", "numero_oficio": "CT-888-LT-2026",
                                "apesar_das_pendencias": True,
                                "justificativa": "fuzz S4 - atalho de etapa a partir de prevista"})
            with db_ro() as c:
                est = c.execute("SELECT estado FROM medicoes WHERE id=?", (mid,)).fetchone()[0]
            reg(rota="POST /api/medicoes/{id}/protocolo", caso=f"S4a protocolo manual de 'prevista' med={mid}",
                esperado="idealmente bloquear (pula nota+envio)", obtido=f"{resumo(rr)} estado_agora={est}",
                flag="FUGIU" if rr.status_code == 201 else "")
            break  # reproduzido 1x aqui; segunda vez já está protocolada

    # S4b: editar valor PROTOCOLADO de medição de espelho (641, espelho_enviado)
    with db_ro() as c:
        em = c.execute("SELECT id FROM medicoes WHERE estado IN ('espelho_gerado','espelho_enviado') AND congelada=0 ORDER BY id DESC LIMIT 1").fetchone()
    if em:
        mid = em[0]
        for _ in range(2):
            rr = eng.put(f"/api/medicoes/{mid}/valor", json={"campo": "protocolado", "valor": "7.777,77"})
            reg(rota="PUT /api/medicoes/{id}/valor", caso=f"S4b editar protocolado de espelho med={mid}",
                esperado="cliente esconde; servidor idealmente trava", obtido=resumo(rr),
                flag="FUGIU" if rr.status_code == 200 else "")

    # S4c: cronograma por API (escrita sem tela)
    for _ in range(2):
        rr = eng.post("/api/contratos/8/cronograma",
                      json={"itens": [{"competencia": "2026-11", "valor": "1.234,56"}]})
        reg(rota="POST /api/contratos/{id}/cronograma", caso="S4c cronograma por API (sem tela)",
            esperado="existe, sem UI", obtido=resumo(rr), flag="FUGIU" if rr.status_code in (200, 201) else "")

    # corpo hostil em rota de estado/valor (sem efeito de envio)
    with db_ro() as c:
        qualquer = c.execute("SELECT id FROM medicoes WHERE estado='protocolada' ORDER BY id DESC LIMIT 1").fetchone()[0]
    casos = {
        "oficio 10k (>40)": lambda: eng.post(f"/api/medicoes/{qualquer}/protocolo",
                                             json={"data": "2026-09-15", "numero_oficio": "A" * 10000}),
        "emoji+HTML no motivo": lambda: eng.post(f"/api/medicoes/{qualquer}/estado",
                                                 json={"estado": "recebida", "motivo": "<script>alert(1)</script> 🚧 teste"}),
        "valor tipo trocado (num)": lambda: eng.put(f"/api/medicoes/{qualquer}/valor",
                                                    json={"campo": "atestado", "valor": 123.45}),
        "valor en-US 1234.56": lambda: eng.put(f"/api/medicoes/{qualquer}/valor",
                                               json={"campo": "atestado", "valor": "1234.56"}),
        "data 31/02 (ISO 2026-02-31)": lambda: eng.post(f"/api/medicoes/{qualquer}/protocolo",
                                                        json={"data": "2026-02-31"}),
        "data ano 9999": lambda: eng.post(f"/api/medicoes/{qualquer}/protocolo", json={"data": "9999-01-01"}),
        "estado inexistente": lambda: eng.post(f"/api/medicoes/{qualquer}/estado", json={"estado": "pago"}),
        "medicao_ids lista vazia (iniciar)": lambda: eng.post("/api/notas/envio/iniciar",
                                                              json={"contrato_id": 8, "medicao_ids": []}),
        "medicao_ids 5000 itens (iniciar)": lambda: eng.post("/api/notas/envio/iniciar",
                                                             json={"contrato_id": 8, "medicao_ids": list(range(5000))}),
    }
    for nome, fn in casos.items():
        try:
            rr = fn()
            flag = "500" if rr.status_code >= 500 else ""
            reg(rota="corpo-hostil", caso=nome, obtido=resumo(rr, 150), flag=flag)
        except Exception as e:
            reg(rota="corpo-hostil", caso=nome, obtido=f"EXC {e}", flag="EXC")

    print("correio:", antes, contar_correio())


if __name__ == "__main__":
    main()
