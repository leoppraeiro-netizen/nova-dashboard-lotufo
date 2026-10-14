"""F02b — refinos: S3 (overflow com documento nfs real), parse_brl árabe (S14 real), S17 (coluna certa)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comum import Cliente, Registro, conferir_simulador, contar_correio, db_ro, resumo

reg = Registro("f02b")


def nfs_doc():
    with db_ro() as c:
        return c.execute("SELECT md.id, md.medicao_id, m.estado FROM medicao_documentos md "
                         "JOIN medicoes m ON m.id=md.medicao_id WHERE md.tipo_doc='nfs' "
                         "ORDER BY md.id DESC LIMIT 1").fetchone()


def main():
    conferir_simulador()
    antes = contar_correio()
    eng = Cliente("engenharia")

    # S3: overflow no INSERT da nota manual, com documento nfs real
    doc = nfs_doc()
    for in_ in range(2):  # reproduzir 2x
        rr = eng.post(f"/api/medicoes/{doc[1]}/notas/manual",
                      json={"documento_id": doc[0], "numero": 123456, "emissao": "2026-09-01",
                            "valor": "99999999999999999999,00"})
        reg(rota="POST /api/medicoes/{id}/notas/manual", caso=f"S3 overflow doc_nfs={doc[0]} med={doc[1]} ({doc[2]})",
            esperado="422 (não 500)", obtido=resumo(rr), flag="500" if rr.status_code >= 500 else "")

    # parse_brl árabe: valor em dígito árabe-índico num campo monetário real (PUT valor)
    with db_ro() as c:
        med = c.execute("SELECT id FROM medicoes WHERE estado='nota_emitida' AND congelada=0 ORDER BY id LIMIT 1").fetchone()
    if med:
        mid = med[0]
        for _ in range(2):
            rr = eng.put(f"/api/medicoes/{mid}/valor", json={"campo": "atestado", "valor": "١٢٣,٤٥", "data": "2026-09-10"})
            with db_ro() as c:
                v = c.execute("SELECT valor_atestado_centavos FROM medicoes WHERE id=?", (mid,)).fetchone()[0]
            reg(rota="PUT /api/medicoes/{id}/valor", caso=f"S14 parse_brl arabe med={mid}",
                esperado="recusa (não é pt-BR)", obtido=f"{resumo(rr)} valor_gravado_centavos={v}",
                flag="FUGIU" if rr.status_code == 200 and v == 12345 else "")

    # S17: número do órgão vazio apaga (coluna protocolos.numero_orgao, caminho _protocolo_enviado)
    with db_ro() as c:
        r = c.execute("SELECT pm.medicao_id, p.id FROM protocolo_medicoes pm JOIN protocolos p ON p.id=pm.protocolo_id "
                      "WHERE p.situacao='enviado' ORDER BY p.id DESC LIMIT 1").fetchone()
    if r:
        mid, pid = r
        eng.post(f"/api/notas/{mid}/numero-orgao", json={"numero": "SIGA-FUZZ-777"})
        with db_ro() as c:
            v1 = c.execute("SELECT numero_orgao FROM protocolos WHERE id=?", (pid,)).fetchone()[0]
        eng.post(f"/api/notas/{mid}/numero-orgao", json={"numero": ""})
        with db_ro() as c:
            v2 = c.execute("SELECT numero_orgao FROM protocolos WHERE id=?", (pid,)).fetchone()[0]
        reg(rota="POST /api/notas/{id}/numero-orgao", caso=f"S17 apaga sem confirmar (protocolo {pid}, med {mid})",
            esperado="confirmação antes de apagar", obtido=f"apos_gravar={v1!r} apos_vazio={v2!r}",
            flag="FUGIU" if v1 == "SIGA-FUZZ-777" and v2 is None else "")

    print("correio:", antes, contar_correio())


if __name__ == "__main__":
    main()
