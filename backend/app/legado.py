"""Remapeamento dos estados do legado para a maquina do espelho (spec §2, carga do legado; bloco 3).

Regra: `nf_emitida` -> `protocolada` (a nota passou a vir ANTES do protocolo; o que era "protocolada e com
NF" e' simplesmente protocolada, com a data da nota guardada em `nota_emitida_em`), `recebida` continua,
`prevista` SEM valor -> `cancelada` (o cronograma ja' guarda o previsto). Uma transacao, auditoria por
medicao; `ensaio=True` relata e desfaz. Roda uma vez em producao, com o servico parado (docs/runbook.md).
"""
from app import auditoria, db

MOTIVO = "remapeamento do legado (bloco 3)"
MOTIVO_PREVISTA = "carga do legado: prevista sem valor"


class _Ensaio(Exception):
    def __init__(self, rel):
        super().__init__("ensaio")
        self.rel = rel


def remapear(conn, usuario_id: int, ensaio: bool) -> dict:
    rel = {"nf_emitida_para_protocolada": 0, "prevista_sem_valor_cancelada": 0, "recebida_mantida": 0,
           "ensaio": ensaio}
    try:
        with db.mutacao(conn):
            rel["recebida_mantida"] = conn.execute("SELECT COUNT(*) FROM medicoes WHERE estado='recebida'").fetchone()[0]
            for m in conn.execute("SELECT id, nf_emitida_em, motivo_represamento FROM medicoes "
                                  "WHERE estado='nf_emitida' ORDER BY id").fetchall():
                data = m["nf_emitida_em"] or conn.execute(
                    "SELECT MIN(n.emissao) FROM nf_alocacoes a JOIN notas_fiscais n ON n.id=a.nota_id "
                    "WHERE a.medicao_id=? AND a.desfeita_em IS NULL", (m["id"],)).fetchone()[0]
                conn.execute("UPDATE medicoes SET estado='protocolada', nota_emitida_em=? WHERE id=? AND estado='nf_emitida'",
                             (data, m["id"]))
                auditoria.registrar(conn, usuario_id, "medicao.estado", "medicao", m["id"],
                                    {"estado": "nf_emitida", "motivo": m["motivo_represamento"]},
                                    {"estado": "protocolada", "motivo": MOTIVO, "nota_emitida_em": data})
                rel["nf_emitida_para_protocolada"] += 1
            for m in conn.execute("SELECT id, motivo_represamento FROM medicoes WHERE estado='prevista' "
                                  "AND valor_protocolado_centavos IS NULL AND valor_atestado_centavos IS NULL "
                                  "ORDER BY id").fetchall():
                conn.execute("UPDATE medicoes SET estado='cancelada', motivo_represamento=? WHERE id=? AND estado='prevista'",
                             (MOTIVO_PREVISTA, m["id"]))
                auditoria.registrar(conn, usuario_id, "medicao.estado", "medicao", m["id"],
                                    {"estado": "prevista", "motivo": m["motivo_represamento"]},
                                    {"estado": "cancelada", "motivo": MOTIVO_PREVISTA})
                rel["prevista_sem_valor_cancelada"] += 1
            if ensaio:
                raise _Ensaio(rel)
    except _Ensaio as e:
        return e.rel
    return rel
