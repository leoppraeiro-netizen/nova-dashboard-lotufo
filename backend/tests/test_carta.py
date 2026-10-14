"""Carta, capa e divisoria em PDF (bloco 5)."""
import datetime
import io

import pypdf

from app import carta


def _texto(pdf: bytes) -> str:
    return "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)


def _carta(**mudar):
    base = dict(numero="CT/301/LT/2026", local_data="Cuiabá/MT, 16 de setembro de 2026.",
                destinatario=["A MT PARTICIPAÇÕES E PROJETOS S.A – MT-PAR"],
                ac=["A/C: Beatriz Exemplo", "Engenheira Fiscal"],
                referencia="Ref.: Contrato n.º 099/2024/MTPAR – Complexo Cultural",
                assunto="Asst.: 23ª Medição contratual (01/08/2026 a 31/08/2026)",
                vocativo="Prezada Senhora,",
                corpo="A LOTUFO encaminha os arquivos da 23ª Medição:\n\ni. Nota fiscal – NF nº 2311\n"
                      "ii. Certidões de regularidade fiscal\n\n# 2. DO PEDIDO\n\nCertos de contar com a usual brevidade.",
                assinatura=["Fernando Exemplo Neto", "Diretor"])
    base.update(mudar)
    return carta.Carta(**base)


def test_carta_leva_os_dados_e_as_marcas_do_corpo():
    t = _texto(carta.gerar(_carta()))
    for trecho in ("CT/301/LT/2026", "16 de setembro de 2026", "A/C: Beatriz Exemplo", "Contrato n.º 099/2024/MTPAR",
                   "23ª Medição contratual", "i. Nota fiscal", "ii. Certidões", "2. DO PEDIDO", "Fernando Exemplo Neto"):
        assert trecho in t, trecho
    assert "# 2." not in t                        # a marca de titulo nao vai para o papel


def test_sem_arial_cai_na_helvetica_sem_quebrar(monkeypatch, tmp_path):
    monkeypatch.setattr(carta, "_ARIAL", tmp_path / "nao-existe.ttf")
    t = _texto(carta.gerar(_carta()))
    assert "MT-PAR" in t and "CT/301/LT/2026" in t


def test_pagina_titulo_e_data_extenso_e_preencher():
    assert "NOTA FISCAL" in _texto(carta.pagina_titulo(["NOTA FISCAL"]))
    assert carta.data_extenso(datetime.date(2026, 9, 16)) == "16 de setembro de 2026"
    assert [carta.ordinal_extenso(n) for n in (7, 27, 110)] == ["sétima", "vigésima sétima", "centésima décima"]
    assert carta.objeto_na_frase("EXECUÇÃO DO REMANESCENTE DA OBRA") == "DO REMANESCENTE DA OBRA"
    assert carta.preencher("{medicao} de {obra} ({faltou})", {"medicao": "23ª Medição", "obra": "Cultural"}) \
        == "23ª Medição de Cultural ({faltou})"


def test_fiscal_vigente_e_emitente_sem_cadastro_de_cartas(tmp_path, monkeypatch):
    from app import db
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    c.execute("INSERT INTO contratos (id, orgao, numero_instrumento, objeto, valor_original_centavos) "
              "VALUES (1,'SINFRA','IC 1','Obra',100)")
    for nome, desde in (("Antigo", "2026-01-01"), ("Novo", "2026-09-16")):
        c.execute("INSERT INTO contrato_fiscais (contrato_id, nome, email, desde) VALUES (1,?,?,?)",
                  (nome, f"{nome}@exemplo.gov.br", desde))
    c.commit()
    assert carta.fiscal_vigente(c, 1, "2026-09-15")["nome"] == "Antigo"
    assert carta.fiscal_vigente(c, 1, "2026-09-16")["nome"] == "Novo"
    em = carta.emitente(c, 1)                          # Lotufo semeada na migracao, sem cartas.yaml aplicado
    assert em["cnpj"] == "31.200.101/0001-30" and em["razao_social"]
    c.close()
