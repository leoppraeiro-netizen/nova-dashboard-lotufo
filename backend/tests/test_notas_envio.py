"""Pagina Notas (plano 2026-10-09): lista a enviar, bloqueio por certidao vencida, envio pelo simulador, envio feito
por fora, aguardando pagamento, regras D1-D9 e a cobranca de certidoes por e-mail."""
import datetime
import io
import json
import zipfile

import pytest

from app import (arquivos, auth, cadastro_aplicar, certidoes, cobranca_certidoes, correio, db, documentos,
                 notas_envio, protocolo, tempo)
from tests.test_protocolo import CARTAS, CINCO, _contrato, _pdf, _textos

D = datetime.date
HOJE = D(2026, 9, 16)


# Cobranca de certidao (geral.yaml, issue #110): conta do Outlook do Leo e os logins dele, ficticios
COBRANCA = {"para": ["leo.outlook@exemplo.com.br"], "enviada_por": ["leo.outlook@exemplo.com.br", "leo@exemplo.com.br"]}


def _cadastro(c, uid, assinados_para=None):
    sinfra = {"protocolo_para": ["sinfra@orgao-a.exemplo.com.br"], "documentos_medicao": CINCO + ["regularidade"],
              "protocolo_copia": ["josi@l.com", "leo.outlook@exemplo.com.br"], "documentos_reajuste": CINCO}
    if assinados_para:
        sinfra["protocolo_assinados_para"] = assinados_para
    cad = {"orgaos": [
        {"chave": "mtpar", "nome": "MTPAR", "familia": "mtpar", "cnpj": None,
         "regras": {"protocolo_para": ["protocolo@orgao-b.exemplo.com.br"], "protocolo_copia": ["josi@l.com"],
                    "carta_destinatario": ["A MT PARTICIPAÇÕES E PROJETOS S.A – MT-PAR"],
                    "ordem_certidoes": ["municipal", "trabalhista", "estadual", "federal", "fgts"],
                    "documentos_medicao": CINCO, "documentos_reajuste": CINCO}},
        {"chave": "sinfra-suef2", "nome": "SINFRA - SUEF II", "familia": "sinfra", "cnpj": None, "regras": sinfra},
        {"chave": "pref-vg", "nome": "Pref. VG", "familia": "prefeitura", "cnpj": None,
         "regras": {"protocolo_para": ["saude@vg.com"], "documentos_medicao": CINCO, "documentos_reajuste": CINCO}}],
        "entidades": [{"chave": "lotufo", "nome": "Lotufo Engenharia e Construções Ltda", "cnpj": "31200101000130",
                       "papel": "lotufo", "coligada_rm": 1, "sigla_oficio": "LT", "nome_curto": "Lotufo"}],
        "contratos": [_contrato("Obra MTPAR", "mtpar", "099/2024/MTPAR"), _contrato("Obra SINFRA", "sinfra-suef2", "IC 1/2026"),
                      _contrato("Obra VG", "pref-vg", "118/2025")],
        "avisos": [], "geral": {"cartas": CARTAS, "cobranca_certidoes": COBRANCA}}
    cad["contratos"][1]["destinatarios_extras"] = ["supervisora@x.com"]
    cadastro_aplicar.aplicar(c, uid, cad)
    ids = {nome: c.execute("SELECT id FROM contratos WHERE nome_curto=?", (f"Obra {nome.upper() if nome != 'vg' else 'VG'}",)
                           ).fetchone()[0] for nome in ("mtpar", "sinfra", "vg")}
    for chave in CINCO:
        rel, sha = arquivos.gravar_bytes("certidoes", _pdf(f"CERTIDAO {chave.upper()}"), "pdf")
        certidoes.registrar(c, uid, 1, documentos.tipo_por_chave(c, chave)["id"], "2026-09-01", "2026-12-31", rel, sha,
                            "upload", natureza="negativa", leitura="automatica")
    rel, sha = arquivos.gravar_bytes("regularidades", _pdf("REGULARIDADE 07/2026"), "pdf")
    documentos.registrar_regularidade(c, uid, 1, "2026-07", rel, sha, 100, "072026 - LOTUFO.pdf")
    for obra in ("mtpar", "sinfra", "vg"):
        for tipo in ("execucao", "reajuste"):
            c.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia, estado, valor_protocolado_centavos, "
                      "nota_emitida_em) VALUES (?, 23, ?, '2026-09', 'nota_emitida', 1000000, '2026-09-15')",
                      (ids[obra], tipo))
            mid = c.execute("SELECT MAX(id) FROM medicoes").fetchone()[0]
            ids[f"{obra}_{'exec' if tipo == 'execucao' else 'reaj'}"] = mid
            rel, sha = arquivos.gravar_bytes("notas", _pdf(f"NFS-e 23{mid:02d}"), "pdf")
            c.execute("INSERT INTO medicao_documentos (medicao_id, fonte, tipo_doc, nome, numero_nf, item_id, arquivo, "
                      "sha256, tamanho) VALUES (?,?,?,?,?,?,?,?,?)",
                      (mid, "operacao", "nfs", f"NFS 23{mid:02d}.pdf", f"23{mid:02d}", f"pdf:{sha}", rel, sha, 10))
    c.commit()
    return ids


def _validade(c, chave, validade):
    c.execute("UPDATE certidoes SET validade=? WHERE tipo_id=(SELECT id FROM certidao_tipos WHERE chave=?)",
              (validade, chave))
    c.commit()


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("DASH_GRAPH_SIMULADOR", str(tmp_path / "sim"))
    monkeypatch.setattr(tempo, "hoje_local", lambda: HOJE)
    c = db.get_conn(); db.migrate(c)
    uid = auth.criar_usuario(c, "Leo", "leo@exemplo.com.br", "senha-forte-123", "admin")
    ids = _cadastro(c, uid)
    ids.update(uid=uid, usuario={"id": uid, "email": "leo@exemplo.com.br"}, sim=tmp_path / "sim")
    yield c, ids
    c.close()


@pytest.fixture
def api(client_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_GRAPH_SIMULADOR", str(tmp_path / "sim"))
    monkeypatch.setattr(tempo, "hoje_local", lambda: HOJE)
    c = db.get_conn()
    ids = _cadastro(c, 1)
    yield client_admin, c, ids
    c.close()


def _por_contrato(lista, cid):
    return [x for x in lista["envios"] if x["contrato_id"] == cid]


# --- lista -----------------------------------------------------------------------------------------

def test_lista_junta_na_sinfra_e_vg_e_separa_na_mtpar(svc):
    c, ids = svc
    lista = notas_envio.a_enviar(c, HOJE)
    sinfra, = _por_contrato(lista, ids["sinfra"])
    assert sinfra["medicao_ids"] == [ids["sinfra_exec"], ids["sinfra_reaj"]]
    assert (sinfra["grupo"], sinfra["orgao_sub"], sinfra["descricao"]) == ("SINFRA", "SUEF II", "23ª medição + reajuste")
    assert sinfra["situacao"] == "pronto" and sinfra["aviso"] is None and sinfra["dias"] == 1
    assert {i["chave"] for i in sinfra["itens"]} == {"notas", "certidoes:lotufo", "regularidade:lotufo"}
    assert len(_por_contrato(lista, ids["mtpar"])) == 2
    vg, = _por_contrato(lista, ids["vg"])                            # D9: VG junta
    assert vg["grupo"] == "Pref. VG" and len(vg["medicao_ids"]) == 2
    assert lista["contadores"] == {"Todas": 4, "MTPAR": 2, "SINFRA": 1, "Pref. VG": 1}


def test_aviso_de_15_dias_e_regularidade_que_falta(svc):
    c, ids = svc
    _validade(c, "municipal", "2026-09-24")
    c.execute("DELETE FROM regularidades"); c.commit()
    sinfra, = _por_contrato(notas_envio.a_enviar(c, HOJE), ids["sinfra"])
    assert sinfra["situacao"] == "pendente"
    assert sinfra["aviso"] == "municipal vence em 8 dias · Falta a regularidade"
    reg = next(i for i in sinfra["itens"] if i["chave"] == "regularidade:lotufo")
    assert (reg["estado"], reg["entidade_id"], reg["competencia"], reg["acao"]) == ("falta", 1, "2026-07",
                                                                                    "anexar_regularidade")
    mtpar = _por_contrato(notas_envio.a_enviar(c, HOJE), ids["mtpar"])[0]
    assert mtpar["situacao"] == "pronto" and "regularidade:lotufo" not in {i["chave"] for i in mtpar["itens"]}


def test_juntar_e_separar_descarta_o_rascunho_anterior(svc):
    c, ids = svc
    p1 = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"]])
    assert notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"]]) == p1
    p2 = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"], ids["sinfra_reaj"]])
    assert p2 != p1 and protocolo.detalhe(c, p1)["situacao"] == "descartado"
    p_vg = notas_envio.iniciar(c, ids["uid"], ids["vg"], [ids["vg_exec"], ids["vg_reaj"]], "254")    # D9: um ofício
    assert len(protocolo.detalhe(c, p_vg)["medicoes"]) == 2
    with pytest.raises(ValueError, match="cada nota"):
        notas_envio.iniciar(c, ids["uid"], ids["mtpar"], [ids["mtpar_exec"], ids["mtpar_reaj"]], "361")


# --- regras do envio (D1-D7) -----------------------------------------------------------------------

def test_sinfra_corpo_pelos_anexos_regularidade_com_nome_novo_e_sem_cno(svc):
    c, ids = svc
    pid = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"], ids["sinfra_reaj"]])
    d = notas_envio.detalhe_envio(c, pid, remetente="leo@exemplo.com.br", hoje=HOJE)
    assert "Seguem, em anexo, notas fiscais, certidões de regularidade e regularidade mensal." in d["previa"]["corpo"]
    nomes = [a["nome"] for a in d["previa"]["anexos"]]
    assert "Regularidade mensal - Lotufo - 07-2026.pdf" in nomes and not any(n.startswith("CNO") for n in nomes)
    assert d["pendencias"] == [] and d["bloqueio"] is None and d["carta"] is None
    protocolo.adicionar_peca(c, ids["uid"], pid, "outro", "Relatorio assinado.pdf", _pdf("RELATORIO"), "pdf")
    d = notas_envio.detalhe_envio(c, pid, hoje=HOJE)
    assert "Relatorio assinado.pdf" in [a["nome"] for a in d["previa"]["anexos"]] and d["pendencias"] == []
    assert "regularidade mensal e relatórios assinados." in d["previa"]["corpo"]


def test_anexo_separado_vai_solto_no_email_e_nao_desfaz_o_montado(svc):
    c, ids = svc
    pid = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"]])
    protocolo.adicionar_peca(c, ids["uid"], pid, protocolo.ANEXO, "Justificativa tecnica.pdf", _pdf("JUSTIFICATIVA"), "pdf")
    d = notas_envio.detalhe_envio(c, pid, hoje=HOJE)
    assert {"nome": "Justificativa tecnica.pdf", "origem": "anexo"}.items() <= next(
        a for a in d["previa"]["anexos"] if a["nome"] == "Justificativa tecnica.pdf").items()
    assert "regularidade mensal e documento complementar." in d["previa"]["corpo"]
    assert [x["nome"] for x in d["extras"]] == ["Justificativa tecnica.pdf"]
    # com carta (MTPAR): fica fora do PDF montado e anexar/remover nao volta o protocolo a rascunho
    pm = notas_envio.iniciar(c, ids["uid"], ids["mtpar"], [ids["mtpar_exec"]], "361")
    paginas = notas_envio.detalhe_envio(c, pm, hoje=HOJE)["carta"]["paginas"]
    protocolo.montar(c, ids["uid"], pm, hoje=HOJE)
    protocolo.adicionar_peca(c, ids["uid"], pm, protocolo.ANEXO, "Justificativa.pdf", _pdf("J"), "pdf")
    d = notas_envio.detalhe_envio(c, pm, hoje=HOJE)
    assert d["situacao_protocolo"] == "montado" and d["carta"]["paginas"] == paginas
    assert "Justificativa.pdf" in [a["nome"] for a in d["previa"]["anexos"]]
    protocolo.remover_peca(c, ids["uid"], pm, d["extras"][0]["id"])
    d = notas_envio.detalhe_envio(c, pm, hoje=HOJE)
    assert d["situacao_protocolo"] == "montado" and d["extras"] == []


def test_zip_do_docusign_entra_como_documento_complementar(api):
    cli, c, ids = api
    pid = notas_envio.iniciar(c, 1, ids["sinfra"], [ids["sinfra_exec"]])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Diagrama_Linear.pdf", _pdf("DIAGRAMA"))
    zipado = buf.getvalue()
    r = cli.post(f"/api/protocolos/{pid}/pecas", data={"tipo": "anexo"},
                 files={"arquivo": ("Complete_com_o_Docusign_Diagrama.zip", zipado, "application/x-zip-compressed")})
    assert r.status_code == 200, r.text
    d = notas_envio.detalhe_envio(c, pid, hoje=HOJE)
    assert [x["nome"] for x in d["extras"]] == ["Complete_com_o_Docusign_Diagrama.zip"]
    assert {"nome": "Complete_com_o_Docusign_Diagrama.zip", "origem": "anexo"}.items() <= next(
        a for a in d["previa"]["anexos"] if a["nome"].startswith("Complete_com")).items()
    # zip fora do documento complementar nao entra (peca tecnica vai dentro do PDF da carta)
    r = cli.post(f"/api/protocolos/{pid}/pecas", data={"tipo": "boletim"},
                 files={"arquivo": ("x.zip", zipado, "application/zip")})
    assert r.status_code == 422
    # PDF disfarcado de zip e' recusado pela assinatura do arquivo
    r = cli.post(f"/api/protocolos/{pid}/pecas", data={"tipo": "anexo"},
                 files={"arquivo": ("falso.zip", _pdf("X"), "application/zip")})
    assert r.status_code == 415


def test_link_do_onedrive_entra_no_corpo_antes_da_assinatura_e_vira_clicavel(svc, monkeypatch):
    c, ids = svc
    monkeypatch.setenv("DASH_SHAREPOINT_HOSTS", "exemplo-my.sharepoint.com,exemplo.sharepoint.com")
    pid = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"]])
    url = "https://exemplo-my.sharepoint.com/:u:/g/personal/leo/IQAbc?e=1&x=2"
    with pytest.raises(ValueError, match="https://"):
        protocolo.adicionar_link(c, ids["uid"], pid, "Documento juntado", "exemplo-my.sharepoint.com/x")
    with pytest.raises(ValueError, match="nome"):
        protocolo.adicionar_link(c, ids["uid"], pid, "  ", url)
    lid = protocolo.adicionar_link(c, ids["uid"], pid, "Documento juntado - 15ª Medição", url)
    d = notas_envio.detalhe_envio(c, pid, hoje=HOJE)
    corpo = d["previa"]["corpo"]
    assert f"Arquivos por link (OneDrive):\nDocumento juntado - 15ª Medição: {url}" in corpo
    assert corpo.index("Arquivos por link") < corpo.index("Atenciosamente")
    assert [x["nome"] for x in d["previa"]["links"]] == ["Documento juntado - 15ª Medição"]
    assert all(a["nome"] != "Documento juntado - 15ª Medição" for a in d["previa"]["anexos"])   # nao e' anexo
    html = protocolo._html(corpo)
    assert '<a href="https://exemplo-my.sharepoint.com/:u:/g/personal/leo/IQAbc?e=1&amp;x=2">' in html
    protocolo.remover_link(c, ids["uid"], pid, lid)
    assert "Arquivos por link" not in notas_envio.detalhe_envio(c, pid, hoje=HOJE)["previa"]["corpo"]


def test_mtpar_assunto_d1_carta_com_fiscal_d3_e_ordem_das_paginas(svc):
    c, ids = svc
    pid = notas_envio.iniciar(c, ids["uid"], ids["mtpar"], [ids["mtpar_exec"]], "361")
    d = notas_envio.detalhe_envio(c, pid, hoje=HOJE)
    assert d["previa"]["assunto"] == "Protocolo CT/361/LT/2026: 23ª Medição, ref. 09/2026, Obra MTPAR"
    assert d["carta"]["paginas"] == ["Ofício CT/361/LT/2026", f"NF 23{ids['mtpar_exec']:02d}",
                                     "Certidão municipal – Lotufo", "Certidão trabalhista – Lotufo",
                                     "Certidão estadual – Lotufo", "Certidão federal – Lotufo", "Certidão FGTS – Lotufo"]
    pagina = _textos(protocolo.montar(c, ids["uid"], pid, hoje=HOJE)["arquivo"])[0]
    assert "A/C: Beatriz Exemplo" in pagina and "Engenheiro(a) Fiscal: Beatriz Exemplo" in pagina


def test_zip_so_com_as_cinco(svc):
    c, ids = svc
    rel, sha = arquivos.gravar_bytes("certidoes", _pdf("FALENCIA"), "pdf")
    certidoes.registrar(c, ids["uid"], 1, documentos.tipo_por_chave(c, "falencia")["id"], "2026-09-01", "2026-10-30",
                        rel, sha, "upload", natureza="negativa", leitura="automatica")
    nome, dados = documentos.zip_vigentes(c, 1, HOJE.isoformat())
    assert len(zipfile.ZipFile(io.BytesIO(dados)).namelist()) == 5


def test_destinatarios_da_nota_com_protocolo_assinados_para(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(tempo, "hoje_local", lambda: HOJE)
    c = db.get_conn(); db.migrate(c)
    uid = auth.criar_usuario(c, "Leo", "leo@exemplo.com.br", "senha-forte-123", "admin")
    ids = _cadastro(c, uid, assinados_para=["fiscal@orgao-a.exemplo.com.br"])
    pid = notas_envio.iniciar(c, uid, ids["sinfra"], [ids["sinfra_exec"]])
    pv = protocolo.previa_envio(c, [pid], hoje=HOJE)
    assert pv["para"] == ["fiscal@orgao-a.exemplo.com.br"]               # sem fiscal e sem extras
    p_vg = notas_envio.iniciar(c, uid, ids["vg"], [ids["vg_exec"]], "254")
    assert protocolo.previa_envio(c, [p_vg], hoje=HOJE)["para"] == ["saude@vg.com", "fiscal@exemplo.gov.br"]
    c.close()


def test_remetente_fora_da_copia_pela_conta_do_outlook(svc, monkeypatch):
    c, ids = svc
    pid = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"]])
    copia = protocolo.previa_envio(c, [pid], remetente="leo@exemplo.com.br", hoje=HOJE)["copia"]
    assert "leo.outlook@exemplo.com.br" in copia               # sem envio anterior: nao se sabe a conta
    monkeypatch.setattr(correio.CorreioSimulado, "remetente", lambda self: "leo.outlook@exemplo.com.br")
    eid = correio.enviar_e_registrar(c, ids["usuario"], "teste", ["x@y.com"],
                                     ["josi@l.com", "Leo.Outlook@exemplo.com.br"], "teste", "<p>a</p>", [])
    assert json.loads(c.execute("SELECT copia FROM envios WHERE id=?", (eid,)).fetchone()[0]) == ["josi@l.com"]
    copia = protocolo.previa_envio(c, [pid], remetente="leo@exemplo.com.br", hoje=HOJE)["copia"]
    assert copia == ["josi@l.com"]


def test_copia_da_obra_soma_a_do_orgao_so_naquele_contrato(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(tempo, "hoje_local", lambda: HOJE)
    c = db.get_conn(); db.migrate(c)
    uid = auth.criar_usuario(c, "Leo", "leo@exemplo.com.br", "senha-forte-123", "admin")
    ids = _cadastro(c, uid, assinados_para=["fiscal@orgao-a.exemplo.com.br"])
    for obra in ("mtpar", "sinfra"):        # o engenheiro de cada obra; repetido e quem ja' esta' no Para nao duplicam
        c.execute("UPDATE contratos SET copia_extras=? WHERE id=?",
                  (json.dumps([f"eng.{obra}@l.com", "josi@l.com", "fiscal@orgao-a.exemplo.com.br"]), ids[obra]))
    c.commit()
    p_mt = notas_envio.iniciar(c, uid, ids["mtpar"], [ids["mtpar_exec"]], "254")
    assert protocolo.previa_envio(c, [p_mt], hoje=HOJE)["copia"] == ["josi@l.com", "eng.mtpar@l.com",
                                                                      "fiscal@orgao-a.exemplo.com.br"]
    p_si = notas_envio.iniciar(c, uid, ids["sinfra"], [ids["sinfra_exec"]])
    assert protocolo.previa_envio(c, [p_si], hoje=HOJE)["copia"] == ["josi@l.com", "leo.outlook@exemplo.com.br",
                                                                      "eng.sinfra@l.com"]
    p_vg = notas_envio.iniciar(c, uid, ids["vg"], [ids["vg_exec"]], "255")
    assert protocolo.previa_envio(c, [p_vg], hoje=HOJE)["copia"] == []
    c.close()


# --- API: bloqueio, envio, por fora, aguardando pagamento ------------------------------------------

def test_certidao_vencida_bloqueia_com_409(api):
    cl, c, ids = api
    _validade(c, "federal", "2026-09-10")
    lista = cl.get("/api/notas/a-enviar").json()
    sinfra, = _por_contrato(lista, ids["sinfra"])
    assert sinfra["situacao"] == "bloqueado" and "federal vencida em 10/09" in sinfra["aviso"]
    pid = cl.post("/api/notas/envio/iniciar", json={"contrato_id": ids["sinfra"],
                                                    "medicao_ids": sinfra["medicao_ids"]}).json()["protocolo_id"]
    d = cl.get(f"/api/notas/envio/{pid}").json()
    assert d["bloqueio"] == "Certidão vencida — renove antes de enviar: Lotufo: federal vencida em 10/09/2026"
    r = cl.post(f"/api/notas/envio/{pid}/enviar", json=_corpo(d, justificativa="mandar assim mesmo, urgente"))
    assert r.status_code == 409, r.text
    assert c.execute("SELECT COUNT(*) FROM envios").fetchone()[0] == 0


def test_envio_pelo_simulador_vira_aguardando_pagamento(api, tmp_path):
    cl, c, ids = api
    r = cl.post("/api/notas/envio/iniciar", json={"contrato_id": ids["sinfra"],
                                                  "medicao_ids": [ids["sinfra_exec"], ids["sinfra_reaj"]]})
    pid = r.json()["protocolo_id"]
    assert _por_contrato(cl.get("/api/notas/a-enviar").json(), ids["sinfra"])[0]["protocolo_id"] == pid
    d = cl.get(f"/api/notas/envio/{pid}").json()
    assert d["etapa"] == "nota" and d["justificativa_obrigatoria"] is False
    r = cl.post(f"/api/notas/envio/{pid}/enviar", json=_corpo(d))
    assert r.status_code == 200, r.text
    enviado = json.loads(sorted((tmp_path / "sim" / "enviados").glob("*.json"))[0].read_text(encoding="utf-8"))
    assert "Regularidade mensal - Lotufo - 07-2026.pdf" in [a["nome"] for a in enviado["anexos"]]
    estados = {r[0] for r in c.execute("SELECT estado || '/' || envio_origem FROM medicoes WHERE id IN (?,?)",
                                       (ids["sinfra_exec"], ids["sinfra_reaj"]))}
    assert estados == {"protocolada/sistema"}
    assert not _por_contrato(cl.get("/api/notas/a-enviar").json(), ids["sinfra"])
    ag = {x["medicao_id"]: x for x in cl.get("/api/notas/aguardando-pagamento").json()}
    x = ag[ids["sinfra_exec"]]
    assert (x["origem"], x["familia"], x["orgao"]) == ("sistema", "sinfra", "SINFRA")
    assert x["enviada_em"] == tempo.para_local(tempo.agora_utc()).date().isoformat()    # data do e-mail, em Cuiaba


def test_envio_feito_por_fora_e_numero_do_siga(api):
    cl, c, ids = api
    r = cl.post("/api/notas/envio-externo",
                data={"medicao_ids": [str(ids["mtpar_exec"])], "enviado_em": "2026-09-15",
                      "observacao": "Enviado pela Maria do Outlook dela"},
                files={"eml": ("envio.eml", b"From: Maria <maria@exemplo.com.br>\r\n"
                                            b"To: protocolo@orgao-b.exemplo.com.br\r\n"
                                            b"Date: Tue, 15 Sep 2026 10:00:00 -0400\r\n"
                                            b"Subject: CT/361\r\n\r\ncorpo", "message/rfc822")})
    assert r.status_code == 200, r.text
    m = c.execute("SELECT estado, envio_origem, envio_externo_em FROM medicoes WHERE id=?",
                  (ids["mtpar_exec"],)).fetchone()
    assert tuple(m) == ("protocolada", "externo", "2026-09-15")
    assert c.execute("SELECT COUNT(*) FROM medicao_documentos WHERE medicao_id=? AND tipo_doc='evidencia_orgao'",
                     (ids["mtpar_exec"],)).fetchone()[0] == 1
    x = next(a for a in cl.get("/api/notas/aguardando-pagamento").json() if a["medicao_id"] == ids["mtpar_exec"])
    assert (x["origem"], x["enviada_em"], x["sem_numero_orgao"]) == ("externo", "2026-09-15", True)
    assert cl.post(f"/api/notas/{ids['mtpar_exec']}/numero-orgao", json={"numero": "MTPARPRO202601234"}).status_code == 200
    x = next(a for a in cl.get("/api/notas/aguardando-pagamento").json() if a["medicao_id"] == ids["mtpar_exec"])
    assert x["numero_orgao"] == "MTPARPRO202601234" and x["sem_numero_orgao"] is False
    r = cl.post("/api/notas/envio-externo", data={"medicao_ids": [str(ids["mtpar_exec"])], "enviado_em": "2026-09-15",
                                                 "observacao": "de novo"})
    assert r.status_code == 422                                         # ja' protocolada


EML = (b"From: Engenharia <engenharia@exemplo.com.br>\r\nTo: sinfra@orgao-a.exemplo.com.br\r\n"
       b"Date: Tue, 15 Sep 2026 10:00:00 -0400\r\nSubject: 23 medicao e reajuste\r\n\r\ncorpo")


def test_envio_por_fora_da_medicao_e_do_reajuste_juntos(api):
    """Issue #172: medicao e reajuste no mesmo e-mail viram um registro so': as duas com o mesmo .eml e uma auditoria."""
    cl, c, ids = api
    par = [ids["sinfra_exec"], ids["sinfra_reaj"]]
    r = cl.post("/api/notas/envio-externo",
                data={"medicao_ids": [str(x) for x in par], "enviado_em": "2026-09-15", "observacao": "Pelo Outlook"},
                files={"eml": ("envio.eml", EML, "message/rfc822")})
    assert r.status_code == 200, r.text
    linhas = c.execute("SELECT estado, envio_origem, envio_externo_em FROM medicoes WHERE id IN (?,?)", par).fetchall()
    assert {tuple(x) for x in linhas} == {("protocolada", "externo", "2026-09-15")}
    emls = c.execute("SELECT medicao_id, arquivo FROM medicao_documentos WHERE tipo_doc='evidencia_orgao'").fetchall()
    assert sorted(x[0] for x in emls) == par and len({x[1] for x in emls}) == 1
    aud = c.execute("SELECT depois FROM audit_log WHERE acao='notas.envio_externo'").fetchall()
    assert len(aud) == 1 and json.loads(aud[0][0])["medicoes"] == par


def test_envio_por_fora_com_a_irma_fora_de_nota_emitida_nao_registra_nenhuma(api):
    cl, c, ids = api
    c.execute("UPDATE medicoes SET estado='espelho_enviado' WHERE id=?", (ids["sinfra_reaj"],)); c.commit()
    r = cl.post("/api/notas/envio-externo",
                data={"medicao_ids": [str(ids["sinfra_exec"]), str(ids["sinfra_reaj"])], "enviado_em": "2026-09-15",
                      "observacao": "Pelo Outlook"}, files={"eml": ("envio.eml", EML, "message/rfc822")})
    assert r.status_code == 422 and "não está com a nota emitida" in r.json()["detail"]
    assert c.execute("SELECT estado FROM medicoes WHERE id=?", (ids["sinfra_exec"],)).fetchone()[0] == "nota_emitida"
    assert c.execute("SELECT COUNT(*) FROM medicao_documentos WHERE tipo_doc='evidencia_orgao'").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM audit_log WHERE acao='notas.envio_externo'").fetchone()[0] == 0


def test_lista_traz_a_irma_em_outro_envio_so_onde_medicao_e_reajuste_vao_juntos(svc):
    """Issue #172: a irma (mesmo numero, outro tipo, nota emitida) fora do envio aparece para o registro por fora."""
    c, ids = svc
    for obra in ("sinfra", "vg", "mtpar"):           # competencias diferentes: a lista nao as junta sozinha
        c.execute("UPDATE medicoes SET competencia='2026-08' WHERE id=?", (ids[f"{obra}_reaj"],))
    c.commit()
    lista = notas_envio.a_enviar(c, HOJE)
    for obra in ("sinfra", "vg"):
        por_medicao = {x["medicao_ids"][0]: x for x in _por_contrato(lista, ids[obra])}
        assert por_medicao[ids[f"{obra}_exec"]]["irmas"] == [
            {"medicao_id": ids[f"{obra}_reaj"], "titulo": "Reajuste da 23ª Medição", "tipo": "reajuste"}]
        assert por_medicao[ids[f"{obra}_reaj"]]["irmas"] == [
            {"medicao_id": ids[f"{obra}_exec"], "titulo": "23ª Medição", "tipo": "execucao"}]
    assert all(x["irmas"] == [] for x in _por_contrato(lista, ids["mtpar"]))       # MTPAR tramita separado
    # irma que nao esta' em nota emitida nao e' oferecida
    c.execute("UPDATE medicoes SET estado='espelho_enviado' WHERE id=?", (ids["sinfra_reaj"],)); c.commit()
    sinfra, = _por_contrato(notas_envio.a_enviar(c, HOJE), ids["sinfra"])
    assert sinfra["irmas"] == []


def test_irma_bloqueada_ou_com_envio_montado_nao_e_oferecida(svc):
    """/code-review da PR do #172: o registro por fora nao pode contornar o bloqueio da irma nem descartar o envio
    montado dela; rascunho continua permitindo."""
    c, ids = svc
    c.execute("UPDATE medicoes SET competencia='2026-08' WHERE id=?", (ids["sinfra_reaj"],)); c.commit()
    pid = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_reaj"]])
    irmas = lambda: next(x for x in _por_contrato(notas_envio.a_enviar(c, HOJE), ids["sinfra"])
                         if x["medicao_ids"] == [ids["sinfra_exec"]])["irmas"]
    assert [i["medicao_id"] for i in irmas()] == [ids["sinfra_reaj"]]               # rascunho: oferece
    c.execute("UPDATE protocolos SET situacao='montado' WHERE id=?", (pid,)); c.commit()
    assert irmas() == []
    c.execute("UPDATE protocolos SET situacao='descartado' WHERE id=?", (pid,)); c.commit()
    _validade(c, "federal", "2026-09-10")                    # vencida: bloqueia a irma (e o envio dela)
    assert irmas() == []


def test_envio_por_fora_recusa_medicoes_de_contratos_diferentes(api):
    cl, c, ids = api
    r = cl.post("/api/notas/envio-externo", data={"medicao_ids": [str(ids["sinfra_exec"]), str(ids["vg_exec"])],
                                                 "enviado_em": "2026-09-15", "observacao": "Pelo Outlook"})
    assert r.status_code == 422 and r.json()["detail"] == "Medição de outro contrato"
    assert c.execute("SELECT COUNT(*) FROM medicoes WHERE estado='protocolada'").fetchone()[0] == 0


def _sem_registro(c, mid):
    assert c.execute("SELECT COUNT(*) FROM medicao_protocolos WHERE medicao_id=?", (mid,)).fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM medicao_documentos WHERE medicao_id=? AND tipo_doc='evidencia_orgao'",
                     (mid,)).fetchone()[0] == 0


def test_registro_por_fora_que_perde_a_corrida_nao_grava_nada(api, monkeypatch):
    """Revisor da PR #178 (aviso 1): o estado e' conferido de novo dentro da transacao. Aqui outro registro protocola
    o reajuste enquanto o .eml e' conferido; sem a nova conferencia, sairia um segundo protocolo e uma segunda
    auditoria. Gate Sol S2: a recusa tambem nao deixa o .eml gravado."""
    cl, c, ids = api
    conferir, antes = notas_envio._e_email, _evidencias()

    def conferir_e_perder(dados):
        c.execute("UPDATE medicoes SET estado='protocolada' WHERE id=?", (ids["sinfra_reaj"],)); c.commit()
        return conferir(dados)
    monkeypatch.setattr(notas_envio, "_e_email", conferir_e_perder)
    r = cl.post("/api/notas/envio-externo",
                data={"medicao_ids": [str(ids["sinfra_exec"]), str(ids["sinfra_reaj"])], "enviado_em": "2026-09-15",
                      "observacao": "Pelo Outlook"}, files={"eml": ("envio.eml", EML, "message/rfc822")})
    assert r.status_code == 422 and "não está com a nota emitida (protocolada)" in r.json()["detail"]
    assert c.execute("SELECT estado FROM medicoes WHERE id=?", (ids["sinfra_exec"],)).fetchone()[0] == "nota_emitida"
    _sem_registro(c, ids["sinfra_exec"]); _sem_registro(c, ids["sinfra_reaj"])
    assert c.execute("SELECT COUNT(*) FROM audit_log WHERE acao='notas.envio_externo'").fetchone()[0] == 0
    assert _evidencias() == antes


def test_dois_registros_por_fora_simultaneos_da_mesma_irma_um_passa(api, monkeypatch):
    """Regra da casa para envio: dois POST simultaneos = 1x200 e 1x422. Os dois passam da primeira conferencia (a
    barreira segura os dois na conferencia do .eml, antes da transacao); so' um protocola a irma."""
    import threading
    cl, c, ids = api
    c.execute("UPDATE medicoes SET competencia='2026-08' WHERE id=?", (ids["sinfra_reaj"],)); c.commit()
    conferir, largada = notas_envio._e_email, threading.Barrier(2)

    def conferir_junto(dados):
        largada.wait(timeout=10)
        return conferir(dados)
    monkeypatch.setattr(notas_envio, "_e_email", conferir_junto)
    pedidos = [{"medicao_ids": [str(ids["sinfra_exec"])], "irma_ids": [str(ids["sinfra_reaj"])]},
               {"medicao_ids": [str(ids["sinfra_reaj"])]}]
    respostas = []

    def dispara(dados):
        respostas.append(cl.post("/api/notas/envio-externo",
                                 data={**dados, "enviado_em": "2026-09-15", "observacao": "Pelo Outlook"},
                                 files={"eml": ("envio.eml", EML, "message/rfc822")}))
    ts = [threading.Thread(target=dispara, args=(p,)) for p in pedidos]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(r.status_code for r in respostas) == [200, 422], [r.text for r in respostas]
    assert c.execute("SELECT COUNT(*) FROM medicao_protocolos WHERE medicao_id=?",
                     (ids["sinfra_reaj"],)).fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM audit_log WHERE acao='notas.envio_externo'").fetchone()[0] == 1


def test_registro_por_fora_recusa_protocolo_com_envio_reservado(api):
    """Revisor da PR #178 (aviso 2): o e-mail esta' saindo pelo sistema; descartar o protocolo reservado faria o
    orgao receber duas vezes."""
    cl, c, ids = api
    c.execute("UPDATE medicoes SET competencia='2026-08' WHERE id=?", (ids["sinfra_reaj"],)); c.commit()
    pid = notas_envio.iniciar(c, 1, ids["sinfra"], [ids["sinfra_reaj"]])
    c.execute("UPDATE protocolos SET envio_reservado_em=datetime('now'), envio_reservado_por=1 WHERE id=?", (pid,))
    c.commit()
    for dados in ({"medicao_ids": [str(ids["sinfra_exec"])], "irma_ids": [str(ids["sinfra_reaj"])]},
                  {"medicao_ids": [str(ids["sinfra_reaj"])]}):
        r = cl.post("/api/notas/envio-externo", data={**dados, "enviado_em": "2026-09-15", "observacao": "Pelo Outlook"})
        assert r.status_code == 422 and "está sendo enviada pelo sistema agora" in r.json()["detail"], r.text
    assert c.execute("SELECT situacao FROM protocolos WHERE id=?", (pid,)).fetchone()[0] == "rascunho"
    _sem_registro(c, ids["sinfra_exec"])


def test_registro_por_fora_recusa_irma_com_envio_montado_mas_aceita_a_medicao_da_pagina(api):
    """Revisor da PR #178 (aviso 2): o servidor reaplica o criterio da lista para a irma marcada; a medicao da propria
    pagina com envio montado continua podendo ser registrada por fora (como antes)."""
    cl, c, ids = api
    c.execute("UPDATE medicoes SET competencia='2026-08' WHERE id=?", (ids["sinfra_reaj"],)); c.commit()
    pid = notas_envio.iniciar(c, 1, ids["sinfra"], [ids["sinfra_reaj"]])
    c.execute("UPDATE protocolos SET situacao='montado' WHERE id=?", (pid,)); c.commit()
    r = cl.post("/api/notas/envio-externo", data={"medicao_ids": [str(ids["sinfra_exec"])],
                                                 "irma_ids": [str(ids["sinfra_reaj"])],
                                                 "enviado_em": "2026-09-15", "observacao": "Pelo Outlook"})
    assert r.status_code == 422 and "registre-a no envio dela" in r.json()["detail"]
    _sem_registro(c, ids["sinfra_exec"])
    assert c.execute("SELECT situacao FROM protocolos WHERE id=?", (pid,)).fetchone()[0] == "montado"
    r = cl.post("/api/notas/envio-externo", data={"medicao_ids": [str(ids["sinfra_reaj"])],
                                                 "enviado_em": "2026-09-15", "observacao": "Pelo Outlook"})
    assert r.status_code == 200, r.text


def test_registro_por_fora_recusa_irma_na_mtpar(api):
    cl, c, ids = api
    r = cl.post("/api/notas/envio-externo", data={"medicao_ids": [str(ids["mtpar_exec"])],
                                                 "irma_ids": [str(ids["mtpar_reaj"])],
                                                 "enviado_em": "2026-09-15", "observacao": "Pelo Outlook"})
    assert r.status_code == 422 and "registre-a no envio dela" in r.json()["detail"]
    _sem_registro(c, ids["mtpar_exec"])


def test_registro_por_fora_so_aceita_varias_medicoes_que_formam_um_envio(api):
    """Gate Sol S1 (PR #178): o cliente nao contorna a conferencia da irma pondo-a entre as medicoes do envio."""
    cl, c, ids = api
    mt = [str(ids["mtpar_exec"]), str(ids["mtpar_reaj"])]
    for dados in ({"medicao_ids": mt},                              # MTPAR tramita separado: nunca um envio so'
                  {"medicao_ids": mt, "irma_ids": [mt[1]]}):        # nas duas listas
        r = cl.post("/api/notas/envio-externo", data={**dados, "enviado_em": "2026-09-15", "observacao": "Pelo Outlook"},
                    files={"eml": ("envio.eml", EML, "message/rfc822")})
        assert r.status_code == 422, r.text
    assert c.execute("SELECT COUNT(*) FROM medicoes WHERE estado='protocolada'").fetchone()[0] == 0
    # SINFRA com o reajuste em envio proprio montado: medicao e reajuste ja' nao sao um envio
    c.execute("UPDATE medicoes SET competencia='2026-08' WHERE id=?", (ids["sinfra_reaj"],)); c.commit()
    pid = notas_envio.iniciar(c, 1, ids["sinfra"], [ids["sinfra_reaj"]])
    c.execute("UPDATE protocolos SET situacao='montado' WHERE id=?", (pid,)); c.commit()
    r = cl.post("/api/notas/envio-externo", data={"medicao_ids": [str(ids["sinfra_exec"]), str(ids["sinfra_reaj"])],
                                                 "enviado_em": "2026-09-15", "observacao": "Pelo Outlook"})
    assert r.status_code == 422 and "não vão no mesmo envio" in r.json()["detail"]
    _sem_registro(c, ids["sinfra_exec"]); _sem_registro(c, ids["sinfra_reaj"])
    assert c.execute("SELECT COUNT(*) FROM audit_log WHERE acao='notas.envio_externo'").fetchone()[0] == 0


def test_irma_no_mesmo_envio_nao_e_oferecida_de_novo(svc):
    c, ids = svc
    sinfra, = _por_contrato(notas_envio.a_enviar(c, HOJE), ids["sinfra"])
    assert len(sinfra["medicao_ids"]) == 2 and sinfra["irmas"] == []


# --- cobranca de certidoes por e-mail --------------------------------------------------------------

def _hora(h, mi=0, dia=HOJE):
    return datetime.datetime(dia.year, dia.month, dia.day, h, mi)


def test_cobranca_de_vencidas_a_cada_2h_e_vencendo_uma_vez_por_dia(svc):
    c, ids = svc
    _validade(c, "federal", "2026-09-10")
    _validade(c, "municipal", "2026-09-24")
    assert cobranca_certidoes.rodada(c, _hora(7, 50)) == []
    assert cobranca_certidoes.rodada(c, _hora(8, 5)) == ["Certidões vencidas (1)", "Certidões vencendo em 15 dias (1)"]
    assert cobranca_certidoes.rodada(c, _hora(9, 40)) == []                # mesma faixa, mesma lista
    assert cobranca_certidoes.rodada(c, _hora(10, 5)) == ["Certidões vencidas (1)"]
    assert cobranca_certidoes.rodada(c, _hora(19, 0)) == []
    enviado = json.loads(sorted((ids["sim"] / "enviados").glob("*.json"))[0].read_text(encoding="utf-8"))
    assert enviado["para"] == ["leo.outlook@exemplo.com.br"] and enviado["copia"] == []
    assert "Lotufo — CND Federal (RFB/PGFN) — validade 10/09/2026 — emitir em: https://" in enviado["corpo"]


def test_cobranca_sem_conta_conectada_so_registra_no_log(svc, monkeypatch):
    c, ids = svc
    monkeypatch.delenv("DASH_GRAPH_SIMULADOR")
    _validade(c, "federal", "2026-09-10")
    assert cobranca_certidoes.rodada(c, _hora(10)) == []
    assert c.execute("SELECT COUNT(*) FROM cobranca_certidoes_envios").fetchone()[0] == 0


def test_cobranca_sem_destinatario_no_cadastro_nao_envia(svc):
    """Issue #110: destinatario e login de quem envia vem do geral.yaml; sem eles, nada sai e nada e' registrado."""
    c, ids = svc
    c.execute("DELETE FROM cadastro_geral WHERE chave='cobranca_certidoes'"); c.commit()
    _validade(c, "federal", "2026-09-10")
    assert cobranca_certidoes.rodada(c, _hora(10)) == []
    assert not (ids["sim"] / "enviados").exists() or not list((ids["sim"] / "enviados").glob("*.json"))
    assert c.execute("SELECT COUNT(*) FROM cobranca_certidoes_envios").fetchone()[0] == 0


# --- testes de quebra 10/10/2026: A-17 (Cco descartado) e A-18 (reajuste irmao fora do e-mail) ------

def _corpo(d, **extra):
    # issue #100: o envio da nota leva sempre os anexos que a previa mostrou
    vistos = [{"nome": a["nome"], "tamanho": a["tamanho"]} for a in d["previa"]["anexos"]]
    return {**{k: d["previa"][k] for k in ("para", "copia", "assunto", "corpo")}, "anexos": vistos, **extra}


def test_cco_do_envio_da_nota_chega_ao_email_e_ao_registro(api, tmp_path):
    cl, c, ids = api
    pid = cl.post("/api/notas/envio/iniciar", json={"contrato_id": ids["sinfra"], "medicao_ids": [
        ids["sinfra_exec"], ids["sinfra_reaj"]]}).json()["protocolo_id"]
    d = cl.get(f"/api/notas/envio/{pid}").json()
    r = cl.post(f"/api/notas/envio/{pid}/enviar", json=_corpo(d, cco=["oculto@exemplo.com"]))
    assert r.status_code == 200, r.text
    enviado = json.loads(sorted((tmp_path / "sim" / "enviados").glob("*.json"))[0].read_text(encoding="utf-8"))
    assert enviado["cco"] == ["oculto@exemplo.com"]
    gravado = c.execute("SELECT cco FROM envios WHERE id=?", (r.json()["envio_id"],)).fetchone()[0]
    assert json.loads(gravado) == ["oculto@exemplo.com"]


IRMA = "Reajuste da 23ª Medição (mesma competência) está com nota emitida e não vai neste e-mail"


def test_sinfra_medicao_sem_o_reajuste_irmao_vira_pendencia(svc):
    c, ids = svc
    pid = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"]])
    pend = notas_envio.detalhe_envio(c, pid, hoje=HOJE)["pendencias"]
    assert [p for p in pend if p.startswith(IRMA)] == [
        IRMA + ": junte pela opção 'Juntar outra nota desta obra' ou justifique"]
    assert "irma_fora" in [p["codigo"] for p in protocolo.previa_envio(c, [pid], hoje=HOJE)["pendencias"]]
    # VG tambem junta (D9); a MTPAR nao junta: cada nota no seu e-mail, sem pendencia
    p_vg = notas_envio.iniciar(c, ids["uid"], ids["vg"], [ids["vg_exec"]], "254")
    assert "irma_fora" in [p["codigo"] for p in protocolo.previa_envio(c, [p_vg], hoje=HOJE)["pendencias"]]
    p_mt = notas_envio.iniciar(c, ids["uid"], ids["mtpar"], [ids["mtpar_exec"]], "361")
    assert "irma_fora" not in [p["codigo"] for p in protocolo.previa_envio(c, [p_mt], hoje=HOJE)["pendencias"]]


def test_reajuste_irmao_em_outro_envio_separado_tambem_cobra(svc):
    """Gate Sol S1 (10/10/2026): dois rascunhos separados nao podem anular o A-18."""
    c, ids = svc
    pid = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"]])
    p_reaj = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_reaj"]])
    assert notas_envio.detalhe_envio(c, pid, hoje=HOJE)["pendencias"] == [
        "Reajuste da 23ª Medição (mesma competência) está em outro envio separado: na SINFRA e na Pref. VG medição "
        "e reajuste vão no mesmo e-mail — junte pela opção 'Juntar outra nota desta obra' (o outro rascunho é "
        "descartado) ou justifique"]
    assert [p.split(" (")[0] for p in notas_envio.detalhe_envio(c, p_reaj, hoje=HOJE)["pendencias"]] == ["23ª Medição"]
    # os dois protocolos no MESMO e-mail: a irma vai junto, nao ha' o que cobrar
    assert "irma_fora" not in [p["codigo"] for p in protocolo.previa_envio(c, [pid, p_reaj], hoje=HOJE)["pendencias"]]


def test_protocolo_ja_enviado_nao_lista_mais_a_irma_fora(svc):
    """Backlog 10/10/2026 (issue #6): depois do envio a pendencia so' informava; rascunho continua cobrando."""
    c, ids = svc
    pid = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"]])
    cods = lambda: [p["codigo"] for p in protocolo.detalhe(c, pid, hoje=HOJE)["pendencias"]]
    assert "irma_fora" in cods()                                          # rascunho: como hoje
    pv = protocolo.previa_envio(c, [pid], hoje=HOJE)
    protocolo.enviar(c, ids["usuario"], [pid], pv["para"], pv["copia"], pv["assunto"], pv["corpo"],
                     justificativa="reajuste vai no próximo e-mail")
    assert protocolo.detalhe(c, pid, hoje=HOJE)["situacao"] == "enviado"
    assert c.execute("SELECT estado FROM medicoes WHERE id=?", (ids["sinfra_reaj"],)).fetchone()[0] == "nota_emitida"
    assert "irma_fora" not in cods()


def test_projeto_e_reajuste_do_mesmo_numero_nao_sao_irmas(svc):
    """Gate Sol S2 (10/10/2026): o par e' execucao x reajuste; projeto e' outra serie."""
    c, ids = svc
    c.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia, estado, valor_protocolado_centavos, "
              "nota_emitida_em) VALUES (?, 23, 'projeto', '2026-09', 'nota_emitida', 1000000, '2026-09-15')",
              (ids["sinfra"],))
    c.commit()
    proj = c.execute("SELECT MAX(id) FROM medicoes").fetchone()[0]
    p_proj = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [proj])
    assert "irma_fora" not in [p["codigo"] for p in protocolo.previa_envio(c, [p_proj], hoje=HOJE)["pendencias"]]
    p_reaj = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_reaj"]])
    irmas = [p["mensagem"] for p in protocolo.previa_envio(c, [p_reaj], hoje=HOJE)["pendencias"]
             if p["codigo"] == "irma_fora"]
    assert [m.split(" (")[0] for m in irmas] == ["23ª Medição"]                  # so' a execucao, nao o projeto


def test_envio_sem_o_reajuste_irmao_exige_justificativa(api):
    cl, c, ids = api
    pid = cl.post("/api/notas/envio/iniciar", json={"contrato_id": ids["sinfra"],
                                                    "medicao_ids": [ids["sinfra_exec"]]}).json()["protocolo_id"]
    d = cl.get(f"/api/notas/envio/{pid}").json()
    assert d["justificativa_obrigatoria"] is True and any(p.startswith(IRMA) for p in d["pendencias"])
    r = cl.post(f"/api/notas/envio/{pid}/enviar", json=_corpo(d))
    assert r.status_code == 422 and "justificativa" in r.json()["detail"]
    assert c.execute("SELECT COUNT(*) FROM envios").fetchone()[0] == 0
    r = cl.post(f"/api/notas/envio/{pid}/enviar", json=_corpo(d, justificativa="reajuste vai no próximo e-mail"))
    assert r.status_code == 200, r.text


# --- testes de quebra 10/10/2026: A-13 (link de qualquer site) e A-11 (qualquer arquivo como .eml) ---

def test_link_so_do_onedrive_ou_sharepoint_da_lotufo(api, monkeypatch):
    cl, c, ids = api
    monkeypatch.setenv("DASH_SHAREPOINT_HOSTS", "exemplo-my.sharepoint.com,exemplo.sharepoint.com")
    pid = cl.post("/api/notas/envio/iniciar", json={"contrato_id": ids["sinfra"], "medicao_ids": [
        ids["sinfra_exec"], ids["sinfra_reaj"]]}).json()["protocolo_id"]
    for url in ("https://exemplo-malicioso.test/x", "https://exemplo-my.sharepoint.com.evil.test/abcdef"):
        r = cl.post(f"/api/protocolos/{pid}/links", json={"nome": "Planilha", "url": url})
        assert r.status_code == 422, url
        assert "exemplo-my.sharepoint.com ou exemplo.sharepoint.com" in r.json()["detail"]
    r = cl.post(f"/api/protocolos/{pid}/links", json={"nome": "Planilha",
                                                      "url": "https://exemplo-my.sharepoint.com/:b:/g/abc"})
    assert r.status_code == 200, r.text
    corpo = cl.get(f"/api/notas/envio/{pid}").json()["previa"]["corpo"]
    assert "exemplo-malicioso" not in corpo and "evil.test" not in corpo


PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x04\x00\x00\x00\x01\x08\x02\x00\x00\x00"


def _evidencias():
    return sorted(arquivos.pasta("evidencias").glob("*"))


def test_envio_por_fora_recusa_arquivo_que_nao_e_email(api):
    cl, c, ids = api
    antes = _evidencias()
    r = cl.post("/api/notas/envio-externo",
                data={"medicao_ids": [str(ids["mtpar_exec"])], "enviado_em": "2026-09-15",
                      "observacao": "Enviado pela Maria do Outlook dela"},
                files={"eml": ("imagem.eml", PNG, "message/rfc822")})
    assert r.status_code == 422
    assert r.json()["detail"].startswith("O arquivo não é um e-mail salvo (.eml)")
    assert c.execute("SELECT estado FROM medicoes WHERE id=?", (ids["mtpar_exec"],)).fetchone()[0] == "nota_emitida"
    assert c.execute("SELECT COUNT(*) FROM medicao_documentos WHERE tipo_doc='evidencia_orgao'").fetchone()[0] == 0
    assert _evidencias() == antes


def test_envio_por_fora_aceita_eml_minimo(api):
    cl, c, ids = api
    eml = (b"From: Maria <maria@exemplo.com.br>\r\nTo: protocolo@orgao-b.exemplo.com.br\r\n"
           b"Date: Tue, 15 Sep 2026 10:00:00 -0400\r\nSubject: CT/361\r\n\r\nSegue a nota.\r\n")
    r = cl.post("/api/notas/envio-externo",
                data={"medicao_ids": [str(ids["mtpar_exec"])], "enviado_em": "2026-09-15",
                      "observacao": "Enviado pela Maria do Outlook dela"},
                files={"eml": ("envio.eml", eml, "message/rfc822")})
    assert r.status_code == 200, r.text
    assert c.execute("SELECT estado FROM medicoes WHERE id=?", (ids["mtpar_exec"],)).fetchone()[0] == "protocolada"


def test_envio_por_fora_recusa_texto_com_from_e_date_escritos_a_mao(api):
    """Gate Sol S3 (10/10/2026): 'From: x' e 'Date: y' digitados num .txt nao fazem um e-mail."""
    cl, c, ids = api
    r = cl.post("/api/notas/envio-externo",
                data={"medicao_ids": [str(ids["mtpar_exec"])], "enviado_em": "2026-09-15",
                      "observacao": "Enviado pela Maria do Outlook dela"},
                files={"eml": ("anotacao.eml", b"From: x\nDate: y\n\nqualquer coisa", "message/rfc822")})
    assert r.status_code == 422 and r.json()["detail"].startswith("O arquivo não é um e-mail salvo (.eml)")
    assert c.execute("SELECT estado FROM medicoes WHERE id=?", (ids["mtpar_exec"],)).fetchone()[0] == "nota_emitida"


# --- testes de quebra 10/10/2026, A-15: numero do orgao vazio nao apaga o gravado ---

def _numero(cl, mid):
    return next(a for a in cl.get("/api/notas/aguardando-pagamento").json() if a["medicao_id"] == mid)["numero_orgao"]


def test_numero_do_orgao_vazio_nao_apaga_no_envio_pelo_sistema(api):
    cl, c, ids = api
    pid = cl.post("/api/notas/envio/iniciar", json={"contrato_id": ids["sinfra"], "medicao_ids": [
        ids["sinfra_exec"], ids["sinfra_reaj"]]}).json()["protocolo_id"]
    d = cl.get(f"/api/notas/envio/{pid}").json()
    assert cl.post(f"/api/notas/envio/{pid}/enviar",
                   json=_corpo(d)).status_code == 200
    mid = ids["sinfra_exec"]
    assert cl.post(f"/api/notas/{mid}/numero-orgao", json={"numero": "X-1"}).status_code == 200
    for vazio in ("", "   "):
        r = cl.post(f"/api/notas/{mid}/numero-orgao", json={"numero": vazio})
        assert r.status_code == 422 and r.json()["detail"] == "Informe o número do protocolo no órgão"
        r = cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": vazio})
        assert r.status_code == 422 and r.json()["detail"] == "Informe o número do protocolo no órgão"
    assert _numero(cl, mid) == "X-1"


def test_numero_do_orgao_vazio_nao_apaga_no_envio_por_fora(api):
    cl, c, ids = api
    mid = ids["mtpar_exec"]
    assert cl.post("/api/notas/envio-externo", data={"medicao_ids": [str(mid)], "enviado_em": "2026-09-15",
                                                     "observacao": "Enviado pela Maria do Outlook dela"}).status_code == 200
    assert cl.post(f"/api/notas/{mid}/numero-orgao", json={"numero": "X-1"}).status_code == 200
    r = cl.post(f"/api/notas/{mid}/numero-orgao", json={"numero": ""})
    assert r.status_code == 422 and r.json()["detail"] == "Informe o número do protocolo no órgão"
    assert _numero(cl, mid) == "X-1"


def _enviar_sinfra(cl, ids):
    pid = cl.post("/api/notas/envio/iniciar", json={"contrato_id": ids["sinfra"], "medicao_ids": [
        ids["sinfra_exec"], ids["sinfra_reaj"]]}).json()["protocolo_id"]
    d = cl.get(f"/api/notas/envio/{pid}").json()
    assert cl.post(f"/api/notas/envio/{pid}/enviar",
                   json=_corpo(d)).status_code == 200
    return pid


def test_comprovante_sozinho_mantem_o_numero_ja_gravado(api):
    """Gate Sol S1 (10/10/2026): numero vazio + comprovante, com numero ja' gravado, salva so' o comprovante."""
    cl, c, ids = api
    pid = _enviar_sinfra(cl, ids)
    assert cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": "X-1"}).status_code == 200
    r = cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": ""},
                files={"comprovante": ("comprovante.pdf", _pdf("comprovante"), "application/pdf")})
    assert r.status_code == 200, r.text
    p = c.execute("SELECT numero_orgao, comprovante_arquivo FROM protocolos WHERE id=?", (pid,)).fetchone()
    assert p["numero_orgao"] == "X-1" and p["comprovante_arquivo"]


def test_comprovante_sem_numero_na_primeira_vez_e_recusado(api):
    """Gate Sol S1: sem numero gravado, o comprovante sozinho nao basta; nada vai para o disco nem para o banco."""
    cl, c, ids = api
    pid = _enviar_sinfra(cl, ids)
    r = cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": " "},
                files={"comprovante": ("comprovante.pdf", _pdf("comprovante"), "application/pdf")})
    assert r.status_code == 422 and r.json()["detail"] == "Informe o número do protocolo junto com o comprovante"
    r = cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": ""})
    assert r.status_code == 422 and r.json()["detail"] == "Informe o número do protocolo no órgão"
    p = c.execute("SELECT numero_orgao, comprovante_arquivo FROM protocolos WHERE id=?", (pid,)).fetchone()
    assert p["numero_orgao"] is None and p["comprovante_arquivo"] is None


def test_comprovante_gravado_baixa_pela_rota_do_protocolo(api):
    """Issue #2: a tela baixa o comprovante pela rota; sem comprovante, 404."""
    cl, c, ids = api
    pid = _enviar_sinfra(cl, ids)
    assert cl.get(f"/api/protocolos/{pid}/comprovante").status_code == 404
    pdf = _pdf("comprovante do orgao")
    r = cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": "X-1"},
                files={"comprovante": ("comprovante.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    assert r.json()["comprovante_arquivo"]                               # a tela decide o link por aqui
    b = cl.get(f"/api/protocolos/{pid}/comprovante")
    assert b.status_code == 200 and b.headers["content-type"] == "application/pdf" and b.content == pdf


def test_trocar_o_comprovante_guarda_o_anterior_na_auditoria(api):
    """Revisao da issue #2: a tela oferece 'Trocar'; o log precisa dizer qual PDF foi substituido."""
    cl, c, ids = api
    pid = _enviar_sinfra(cl, ids)
    files = lambda t: {"comprovante": ("c.pdf", _pdf(t), "application/pdf")}          # noqa: E731
    p1 = cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": "X-1"}, files=files("um")).json()["comprovante_arquivo"]
    p2 = cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": ""}, files=files("dois")).json()["comprovante_arquivo"]
    assert p1 != p2
    a = c.execute("SELECT antes, depois FROM audit_log WHERE acao='protocolo.numero_orgao' AND entidade_id=? "
                  "ORDER BY id DESC LIMIT 1", (str(pid),)).fetchone()
    assert json.loads(a["antes"])["comprovante"] == p1 and json.loads(a["depois"])["comprovante"] == p2


def test_comprovante_que_nao_e_pdf_ou_passa_do_limite_e_recusado_em_portugues(api):
    cl, c, ids = api
    pid = _enviar_sinfra(cl, ids)
    r = cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": "X-1"},
                files={"comprovante": ("c.png", b"\x89PNG\r\n", "image/png")})
    assert r.status_code == 415 and r.json()["detail"].startswith("Envie um PDF")
    r = cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": "X-1"},
                files={"comprovante": ("c.pdf", b"nao e pdf", "application/pdf")})
    assert r.status_code == 415 and "não é um PDF" in r.json()["detail"]
    grande = b"%PDF-1.4\n" + b"0" * arquivos.TETO_BYTES
    r = cl.post(f"/api/protocolos/{pid}/numero-orgao", data={"numero": "X-1"},
                files={"comprovante": ("c.pdf", grande, "application/pdf")})
    assert r.status_code == 413 and r.json()["detail"] == "Arquivo acima do limite de 10 MB"
    p = c.execute("SELECT numero_orgao, comprovante_arquivo FROM protocolos WHERE id=?", (pid,)).fetchone()
    assert p["numero_orgao"] is None and p["comprovante_arquivo"] is None


# --- issue #100: os anexos da previa conferidos tambem no Enviar a nota ------------------------------

def test_nf_anexada_depois_da_previa_recusa_o_envio_da_nota_sem_reservar(api, tmp_path):
    """Revisor adversarial na PR #92: a tela Enviar a nota manda os anexos que a pessoa viu; NF anexada a' medicao
    com a previa aberta faz o servidor recusar antes de reservar, com a mesma mensagem do protocolo."""
    cl, c, ids = api
    pid = cl.post("/api/notas/envio/iniciar", json={"contrato_id": ids["sinfra"], "medicao_ids": [
        ids["sinfra_exec"], ids["sinfra_reaj"]]}).json()["protocolo_id"]
    d = cl.get(f"/api/notas/envio/{pid}").json()
    vistos = [{"nome": a["nome"], "tamanho": a["tamanho"]} for a in d["previa"]["anexos"]]
    assert vistos
    rel, sha = arquivos.gravar_bytes("notas", _pdf("FRC ASSINADA"), "pdf")
    c.execute("INSERT INTO medicao_documentos (medicao_id, fonte, tipo_doc, nome, numero_nf, item_id, arquivo, sha256, "
              "tamanho) VALUES (?,?,?,?,?,?,?,?,?)",
              (ids["sinfra_exec"], "operacao", "fatura", "FRC 77.pdf", "77", f"pdf:{sha}", rel, sha, 10))
    c.commit()
    assert len(cl.get(f"/api/notas/envio/{pid}").json()["previa"]["anexos"]) == len(vistos) + 1
    r = cl.post(f"/api/notas/envio/{pid}/enviar", json=_corpo(d, anexos=vistos))
    assert r.status_code == 422, r.text
    # gate Sol S2 (PR #141): a recusa traz `codigo`, para a tela recarregar so' nela e nao em qualquer erro
    assert r.json()["detail"] == {"codigo": "ANEXOS_MUDARAM", "mensagem": (
        "Os anexos mudaram depois da prévia: descarte esta prévia e abra outra para conferir o que vai no e-mail")}
    p = c.execute("SELECT situacao, envio_id, envio_reservado_em FROM protocolos WHERE id=?", (pid,)).fetchone()
    assert tuple(p) == ("rascunho", None, None)
    assert c.execute("SELECT COUNT(*) FROM envios").fetchone()[0] == 0
    assert not list((tmp_path / "sim").glob("enviados/*.json"))
    # a previa nova (com a FRC) envia
    d = cl.get(f"/api/notas/envio/{pid}").json()
    r = cl.post(f"/api/notas/envio/{pid}/enviar", json=_corpo(d))
    assert r.status_code == 200, r.text


def test_envio_da_nota_sem_os_anexos_da_previa_e_recusado(api):
    """Revisor adversarial na PR #141: sem a lista (aba aberta antes do deploy, chamada direta) nao envia sem conferir."""
    cl, c, ids = api
    pid = cl.post("/api/notas/envio/iniciar", json={"contrato_id": ids["sinfra"], "medicao_ids": [
        ids["sinfra_exec"], ids["sinfra_reaj"]]}).json()["protocolo_id"]
    corpo = _corpo(cl.get(f"/api/notas/envio/{pid}").json())
    del corpo["anexos"]
    r = cl.post(f"/api/notas/envio/{pid}/enviar", json=corpo)
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "anexos"]
    assert c.execute("SELECT COUNT(*) FROM envios").fetchone()[0] == 0


def test_envio_da_nota_por_dentro_exige_os_anexos_da_previa(svc):
    """Gate Sol S1 (PR #141): chamador interno sem a lista (ou com None) nao envia sem conferir nem reserva."""
    c, ids = svc
    pid = notas_envio.iniciar(c, ids["uid"], ids["sinfra"], [ids["sinfra_exec"], ids["sinfra_reaj"]])
    pv = protocolo.previa_envio(c, [pid], hoje=HOJE)
    args = (c, ids["usuario"], pid, pv["para"], pv["copia"], pv["assunto"], pv["corpo"], None)
    with pytest.raises(TypeError):
        notas_envio.enviar(*args)                                   # anexos_previa e' obrigatorio, so' por nome
    with pytest.raises(ValueError, match="anexos da prévia"):
        notas_envio.enviar(*args, anexos_previa=None)
    p = c.execute("SELECT situacao, envio_id, envio_reservado_em FROM protocolos WHERE id=?", (pid,)).fetchone()
    assert tuple(p) == ("rascunho", None, None)
    assert c.execute("SELECT COUNT(*) FROM envios").fetchone()[0] == 0
