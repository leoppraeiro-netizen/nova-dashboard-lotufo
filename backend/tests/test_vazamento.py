"""scripts/vazamento.py (issue #106): barra CNPJ/CPF validos, e-mail real, chave de NFS-e/NF-e, nome da maquina,
nomes da lista local e binario nao lido, e mostra so' o dado mascarado. Os valores "proibidos" sao montados aqui na
hora: escrever o dado no teste faria a varredura barrar o proprio teste."""
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "vazamento.py"

_spec = importlib.util.spec_from_file_location("vazamento", SCRIPT)
vazamento = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vazamento)

NBSP = " "
GOV = vazamento.SUFIXO_GOV
DOM_LOTUFO_ENG, DOM_GRUPO_COM, DOM_GRUPO_SRV = vazamento.DOMINIOS_PROIBIDOS[:3]
EMAIL_REAL = "fulano@" + DOM_LOTUFO_ENG
SERVIDOR = "srv-teste-xyz9"


def _dv_alfa(texto: str, pesos: list) -> int:
    resto = sum((ord(c) - 48) * p for c, p in zip(texto, pesos)) % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_valido_inventado(base12: str = "741852960001") -> str:
    """CNPJ com os dois digitos verificadores certos, calculado aqui (independente do script). Aceita letras."""
    d1 = _dv_alfa(base12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = _dv_alfa(base12 + str(d1), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return base12 + str(d1) + str(d2)


def cpf_valido_inventado(base9: str = "529982247") -> str:
    d1 = sum(int(d) * p for d, p in zip(base9, range(10, 1, -1))) * 10 % 11 % 10
    d2 = sum(int(d) * p for d, p in zip(base9 + str(d1), range(11, 1, -1))) * 10 % 11 % 10
    return base9 + str(d1) + str(d2)


def formatado(cnpj: str) -> str:
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def errado(digitos: str) -> str:
    return digitos[:-1] + str((int(digitos[-1]) + 1) % 10)


def chave_nfse(cnpj: str) -> str:
    """50 digitos: municipio(7) + ambiente(1) + tipo de inscricao(1) + CNPJ(14) + resto."""
    return "5103403" + "1" + "2" + cnpj + "0" * 27


def chave_nfe(cnpj: str) -> str:
    """44 digitos: UF(2) + AAMM(4) + CNPJ(14) + resto."""
    return "35" + "2608" + cnpj + "0" * 24


def varrer(texto, excecoes=None, termos=(), servidores=()):
    return vazamento.varrer("arq.txt", texto, excecoes or vazamento.Excecoes(), termos, servidores)


def tipos(texto, **kw):
    return [a[2] for a in varrer(texto, **kw)]


def test_acha_cnpj_email_e_maquina_e_mascara_os_tres():
    cnpj = formatado(cnpj_valido_inventado())
    texto = f"empresa {cnpj}\ncontato {EMAIL_REAL}\nrodando em {SERVIDOR} hoje\n"
    achados = varrer(texto, servidores={SERVIDOR})
    assert [(a[1], a[2]) for a in achados] == [(1, "CNPJ valido"), (2, "e-mail real"),
                                               (3, "nome da maquina de producao")]
    saida = "\n".join(a[3] for a in achados)
    assert cnpj not in saida and "fulano" not in saida and SERVIDOR not in saida
    assert cnpj[:7] + "***" in saida and "fu***@" in saida and SERVIDOR[:2] + "***" in saida


def test_cnpj_sem_formatacao_e_cpf_validos_sao_achados_e_digito_errado_nao():
    cnpj, cpf = cnpj_valido_inventado(), cpf_valido_inventado()
    assert len(varrer(f"x {cnpj} y")) == 1
    assert len(varrer(f"x {cpf} y")) == 1
    assert len(varrer(f"CPF {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}")) == 1
    assert varrer(f"x {errado(cnpj)} y") == []
    assert varrer(f"x {errado(cpf)} y") == []
    assert varrer("11111111111 e 00000000000000") == []


def test_cnpj_com_separador_irregular_e_achado():
    c = cnpj_valido_inventado()
    variantes = {
        "barra sem pontos": f"{c[:8]}/{c[8:12]}-{c[12:]}",
        "espacos": " ".join([c[:2], c[2:5], c[5:8], c[8:12], c[12:]]),
        "espaco inseparavel": NBSP.join([c[:2], c[2:5], c[5:8], c[8:12], c[12:]]),
        "hifen no lugar da barra": f"{c[:2]}.{c[2:5]}.{c[5:8]}-{c[8:12]}-{c[12:]}",
        "so ponto": f"{c[:2]}.{c[2:5]}.{c[5:8]}.{c[8:12]}.{c[12:]}",
    }
    for nome, texto in variantes.items():
        assert tipos(f"CNPJ {texto} ok") == ["CNPJ valido"], nome
        assert varrer(f"CNPJ {errado(texto)} ok") == [], nome


def test_cnpj_alfanumerico_formatado_e_achado():
    c = cnpj_valido_inventado("7A1B5C9D0001")
    assert tipos(f"CNPJ {formatado(c)}") == ["CNPJ valido"]
    assert varrer(f"CNPJ {formatado(errado(c))}") == []


def test_excecao_vale_em_qualquer_formatacao_e_so_para_o_que_esta_na_lista():
    cnpj, outro = cnpj_valido_inventado(), cnpj_valido_inventado("741852960002")
    exc = vazamento.Excecoes(documentos={cnpj})
    assert varrer(f"{formatado(cnpj)} e {cnpj} e {cnpj[:8]}/{cnpj[8:12]}-{cnpj[12:]}", exc) == []
    assert len(varrer(f"{formatado(outro)}", exc)) == 1


def test_email_gov_br_so_passa_se_for_do_dominio_ficticio():
    orgao, fake = f"orgao.{GOV}", f"fake.{GOV}"
    assert varrer(f"a@exemplo.{GOV}") == []
    assert len(varrer(f"a@cuiaba.mt.{GOV}")) == 1
    assert len(varrer(f"a@{orgao}")) == 1
    assert len(varrer("a@setor." + DOM_LOTUFO_ENG)) == 1
    assert varrer("a@exemplo.com.br e b@gmail.com") == []
    exc = vazamento.Excecoes(emails={f"a@{orgao}"}, dominios={fake})
    assert varrer(f"a@{orgao} x@{fake}", exc) == []
    assert len(varrer(f"b@{orgao}", exc)) == 1


def test_email_do_grupo_e_qualquer_dominio_com_o_nome_da_empresa_sao_barrados():
    assert tipos(f"fulano@{DOM_GRUPO_COM}") == ["e-mail real"]
    assert tipos(f"fulano@{DOM_GRUPO_SRV}") == ["e-mail real"]
    assert tipos("fulano@mail." + "lotufo" + ".dev") == ["e-mail real"]
    assert tipos("fulano@" + "outro-lotufo" + ".net") == ["e-mail real"]
    assert varrer("fulano@lotufo.com") == []


def test_chave_de_acesso_de_nfse_e_de_nfe_fora_da_lista():
    cnpj = cnpj_valido_inventado()
    nfse, nfe = chave_nfse(cnpj), chave_nfe(cnpj)
    assert tipos(f"chave {nfse}") == ["chave de acesso de NFS-e"]
    assert tipos(f"chave {nfe}") == ["chave de acesso de NF-e"]
    assert varrer(f"chave {nfse}", vazamento.Excecoes(documentos={nfse, cnpj})) == []


def test_chave_em_grupos_de_quatro_com_espaco_tambem_e_achada():
    nfse = chave_nfse(cnpj_valido_inventado())
    em_grupos = " ".join(nfse[i:i + 4] for i in range(0, 48, 4)) + " " + nfse[48:]
    assert tipos(f"chave {em_grupos}") == ["chave de acesso de NFS-e"]
    nfe = chave_nfe(cnpj_valido_inventado())
    assert tipos("chave " + NBSP.join(nfe[i:i + 4] for i in range(0, 44, 4))) == ["chave de acesso de NF-e"]
    assert varrer("numeros " + " ".join(["1234"] * 5)) == []


def test_cnpj_do_emissor_dentro_da_chave_nao_fica_escondido_pela_chave_liberada():
    cnpj = cnpj_valido_inventado()
    chave = chave_nfse(cnpj)
    assert tipos(f"x {chave}", excecoes=vazamento.Excecoes(documentos={chave})) == ["CNPJ valido (emissor da chave)"]
    assert varrer(f"x {chave}", vazamento.Excecoes(documentos={chave, cnpj})) == []


def test_nome_da_lista_local_sem_acento_caixa_ou_separador():
    termo = ["maria souza"]
    for texto in ("falei com MARIA Souza ontem", "maria.souza@exemplo.com.br", "arquivo_maria_souza.pdf",
                  "MARIA  SOUZA", f"maria{NBSP}souza", "María-Souza", "maria\tsouza"):
        assert tipos(texto, termos=termo) == ["nome de pessoa da lista local"], texto
    assert tipos("falou com José Antônio", termos=["jose antonio"]) == ["nome de pessoa da lista local"]
    assert tipos("falou com jose antonio", termos=["José Antônio"]) == ["nome de pessoa da lista local"]
    assert varrer("marianas souzas", termos=["maria souza"]) == []
    assert varrer("mariasouza", termos=termo) == []


def test_nome_mascarado_mostra_pouco_e_acento_nao_desloca_o_trecho():
    achados = varrer("José Antônio assinou", termos=["jose antonio"])
    assert achados[0][3].startswith("Jo***") and "Antonio" not in achados[0][3] and "Ant" not in achados[0][3]


def test_servidor_barrado_com_pontuacao_e_sem_diferenca_de_caixa():
    assert tipos(f"\\\\{SERVIDOR.upper()}\\c$", servidores={SERVIDOR}) == ["nome da maquina de producao"]
    assert tipos(f"{SERVIDOR.replace('-', '.')}", servidores={SERVIDOR}) == ["nome da maquina de producao"]
    assert varrer(f"{SERVIDOR}x", servidores={SERVIDOR}) == []


def test_nao_ha_nome_de_maquina_nem_hash_no_script():
    assert not hasattr(vazamento, "HASHES_SERVIDOR")
    assert "sha256" not in SCRIPT.read_text(encoding="utf-8").lower().replace("sha256:", "x")


def test_trecho_mascara_tambem_o_vizinho_liberado_por_excecao():
    liberado, novo = cnpj_valido_inventado(), cnpj_valido_inventado("741852960002")
    exc = vazamento.Excecoes(documentos={liberado})
    achados = varrer(f"{formatado(liberado)}, {formatado(novo)}", exc)
    assert len(achados) == 1
    assert formatado(liberado) not in achados[0][3] and formatado(novo) not in achados[0][3]


def test_mascara_de_cpf_chave_e_nome_mostra_pouco():
    cpf = cpf_valido_inventado()
    assert vazamento.mascarar(cpf, 3) == cpf[:3] + "***"
    assert vazamento.mascarar("abc", 6) == "ab***"


def test_arquivo_de_excecoes_so_aceita_cnpj_de_raiz_ficticia_e_nao_conhece_hash():
    fic = formatado(cnpj_valido_inventado("312001010001"))
    exc = vazamento.Excecoes.de_texto("# comentario\n\n" + fic + "  # ficticio\n@fake." + GOV + "\n"
                                      + cpf_valido_inventado() + "\n")
    assert exc.documentos >= {cnpj_valido_inventado("312001010001"), cpf_valido_inventado()}
    assert exc.dominios == {"fake." + GOV}
    # os tres CNPJs de exemplo de geradores publicos ja' vem liberados
    assert vazamento.CNPJS_DE_EXEMPLO <= exc.documentos
    with pytest.raises(ValueError, match="raiz ficticia"):
        vazamento.Excecoes.de_texto(formatado(cnpj_valido_inventado()) + "\n")
    with pytest.raises(ValueError):
        vazamento.Excecoes.de_texto("sha256:" + "a" * 64 + "\n")
    with pytest.raises(ValueError):
        vazamento.Excecoes.de_texto("qualquer coisa\n")


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-c", "commit.gpgsign=false", *args],
                   cwd=repo, check=True, capture_output=True)


def _repo_temporario(tmp_path, arquivos: dict):
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts" / "vazamento.py")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for nome, conteudo in arquivos.items():
        caminho = tmp_path / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(conteudo, bytes):
            caminho.write_bytes(conteudo)
        else:
            caminho.write_text(conteudo, encoding="utf-8")
    return tmp_path


def _git_saida(repo, *args) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _rodar(repo, *args, servidor=None, extra=None, entrada=None):
    ambiente = {k: v for k, v in os.environ.items() if k != "DASH_SERVIDOR"}
    if servidor:
        ambiente["DASH_SERVIDOR"] = servidor
    ambiente.update(extra or {})
    return subprocess.run([sys.executable, "scripts/vazamento.py", *args], cwd=repo, env=ambiente,
                          capture_output=True, text=True, encoding="utf-8", input=entrada)


def _docx(texto: str, extras: dict = None) -> bytes:
    """.docx minimo; `texto` vai dentro de um unico <w:t>, `extras` sao outras partes (caminho -> conteudo)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", f"<w:document><w:t>{texto}</w:t></w:document>")
        for caminho, conteudo in (extras or {}).items():
            zf.writestr(caminho, conteudo)
    return buf.getvalue()


def test_script_falha_listando_os_tres_achados_mascarados(tmp_path):
    cnpj = formatado(cnpj_valido_inventado())
    repo = _repo_temporario(tmp_path, {"vazou.txt": f"CNPJ {cnpj}\nmail {EMAIL_REAL}\nhost {SERVIDOR}\n",
                                       "limpo.txt": "nada aqui\n"})
    _git(repo, "add", ".")
    r = _rodar(repo, servidor=SERVIDOR)
    assert r.returncode == 1, r.stdout + r.stderr
    linhas = r.stdout.splitlines()
    assert len(linhas) == 3 and all(linha.startswith("vazou.txt:") for linha in linhas)
    assert "vazou.txt:1: CNPJ valido" in r.stdout and "vazou.txt:2: e-mail real" in r.stdout
    assert "vazou.txt:3: nome da maquina de producao" in r.stdout
    assert cnpj not in r.stdout and "fulano" not in r.stdout and SERVIDOR not in r.stdout
    assert "limpo.txt" not in r.stdout


def test_script_termina_com_zero_quando_nao_ha_o_que_barrar_e_avisa_que_pulou_a_maquina(tmp_path):
    repo = _repo_temporario(tmp_path, {"a.txt": "so texto e a@exemplo.gov.br\n"})
    _git(repo, "add", ".")
    r = _rodar(repo)
    assert r.returncode == 0
    assert "sem DASH_SERVIDOR" in r.stderr
    assert "sem DASH_SERVIDOR" not in _rodar(repo, servidor=SERVIDOR).stderr


def test_staged_olha_so_o_que_esta_no_indice(tmp_path):
    cnpj = formatado(cnpj_valido_inventado())
    repo = _repo_temporario(tmp_path, {"limpo.txt": "ok\n", "fora_do_commit.txt": cnpj})
    _git(repo, "add", "limpo.txt")
    assert _rodar(repo, "--staged").returncode == 0
    # no indice o arquivo tem o dado; depois o disco muda de novo e o hook ainda barra
    (repo / "limpo.txt").write_text(cnpj, encoding="utf-8")
    _git(repo, "add", "limpo.txt")
    (repo / "limpo.txt").write_text("ok de novo\n", encoding="utf-8")
    r = _rodar(repo, "--staged")
    assert r.returncode == 1 and "limpo.txt:1: CNPJ valido" in r.stdout and cnpj not in r.stdout


def test_staged_le_a_lista_de_excecoes_do_indice_e_nao_do_disco(tmp_path):
    cnpj = cnpj_valido_inventado("312001010001")
    repo = _repo_temporario(tmp_path, {"a.txt": formatado(cnpj) + "\n", "scripts/vazamento-excecoes.txt": cnpj + "\n"})
    _git(repo, "add", "a.txt")
    assert _rodar(repo, "--staged").returncode == 1        # a lista existe so' no disco
    _git(repo, "add", "scripts/vazamento-excecoes.txt")
    assert _rodar(repo, "--staged").returncode == 0        # agora esta' no indice
    (repo / "scripts" / "vazamento-excecoes.txt").write_text("", encoding="utf-8")
    assert _rodar(repo, "--staged").returncode == 0        # editar o disco depois nao muda o que vai no commit


def _repo_com_base(tmp_path, lista_na_base):
    """master com (ou sem) a lista de excecoes e uma branch `pr` partindo dela."""
    cnpj = cnpj_valido_inventado("312001010001")
    arquivos = {"a.txt": "ok\n"}
    if lista_na_base:
        arquivos["scripts/vazamento-excecoes.txt"] = formatado(cnpj) + "\n"
    repo = _repo_temporario(tmp_path, arquivos)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "branch", "-M", "master")
    _git(repo, "checkout", "-q", "-b", "pr")
    return repo, cnpj


def test_base_falha_quando_a_pr_altera_a_lista_de_excecoes(tmp_path):
    repo, cnpj = _repo_com_base(tmp_path, lista_na_base=True)
    assert _rodar(repo, "--base", "master").returncode == 0           # sem mudanca na lista
    (repo / "scripts" / "vazamento-excecoes.txt").write_text(
        formatado(cnpj) + "\n" + formatado(cnpj_valido_inventado("312001010002")) + "\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "mexe na lista")
    r = _rodar(repo, "--base", "master")
    assert r.returncode == 1 and "exige merge do Leo" in r.stderr
    assert _rodar(repo).returncode == 0                                # sem --base a varredura sozinha passa


def test_base_nao_conta_a_primeira_vez_que_a_lista_aparece(tmp_path):
    repo, cnpj = _repo_com_base(tmp_path, lista_na_base=False)
    (repo / "scripts" / "vazamento-excecoes.txt").write_text(formatado(cnpj) + "\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "cria a lista")
    assert _rodar(repo, "--base", "master").returncode == 0


def test_docx_e_xlsx_sao_abertos_e_o_xml_de_dentro_e_varrido(tmp_path):
    cnpj = formatado(cnpj_valido_inventado())
    repo = _repo_temporario(tmp_path, {"limpo.docx": _docx("nada"), "sujo.docx": _docx(f"CNPJ {cnpj}")})
    _git(repo, "add", ".")
    r = _rodar(repo)
    assert r.returncode == 1 and "sujo.docx!word/document.xml:1: CNPJ valido" in r.stdout
    assert "limpo.docx" not in r.stdout and cnpj not in r.stdout


def test_binario_fora_da_lista_falha_e_pdf_so_passa_nas_fixtures(tmp_path):
    repo = _repo_temporario(tmp_path, {"img/logo.png": b"\x89PNG\0\0", "fonte.woff2": b"wOF2\0\0",
                                       "backend/tests/fixtures/certidao.pdf": b"%PDF\0\0"})
    _git(repo, "add", ".")
    assert _rodar(repo).returncode == 0
    (repo / "docs").mkdir()
    (repo / "docs" / "certidao.pdf").write_bytes(b"%PDF\0\0")
    (repo / "dados.bin").write_bytes(b"\0\1\2")
    _git(repo, "add", ".")
    r = _rodar(repo)
    assert r.returncode == 1
    assert "docs/certidao.pdf: binario fora da lista permitida (.pdf)" in r.stdout
    assert "dados.bin: binario fora da lista permitida (.bin)" in r.stdout
    assert "logo.png" not in r.stdout and "fixtures" not in r.stdout


def test_cpf_com_separador_irregular_e_achado_mas_data_com_hifen_nao_vira_cpf():
    c = cpf_valido_inventado()
    variantes = [f"{c[:9]}-{c[9:]}", " ".join([c[:3], c[3:6], c[6:9], c[9:]]), NBSP.join([c[:3], c[3:6], c[6:9], c[9:]]),
                 f"{c[:3]}.{c[3:6]}.{c[6:9]}.{c[9:]}", f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"]
    for texto in variantes:
        assert tipos(f"CPF {texto} ok") == ["CPF valido"], texto
        assert varrer(f"CPF {errado(texto)} ok") == [], texto
    assert varrer("backup-163-20260904-080833.db") == []


def test_dominio_solto_e_forma_codificada_de_url_tambem_sao_barrados():
    assert tipos(f"remetente @{DOM_GRUPO_SRV} fixo") == ["e-mail real"]
    assert tipos(f"mailto:fulano%40{DOM_GRUPO_COM}") == ["e-mail real"]
    assert tipos(f"x%40{DOM_LOTUFO_ENG}") == ["e-mail real"]
    mascarado = varrer(f"fulano%40{DOM_GRUPO_COM}")[0][3]
    assert mascarado.startswith("fu***@") and "fulano" not in mascarado
    assert varrer("@pytest.fixture e @app.get e a%40exemplo.com.br") == []
    assert varrer(f"a%40exemplo.{GOV} @exemplo.{GOV}") == []


def test_cnpj_e_email_partidos_entre_dois_trechos_do_word_sao_achados(tmp_path):
    c = cnpj_valido_inventado()
    cnpj = formatado(c)
    partido = f"{cnpj[:6]}</w:t></w:r><w:r><w:rPr/><w:t>{cnpj[6:]}"
    email = f"fulano@{DOM_GRUPO_COM}"
    email_partido = f"{email[:4]}</w:t></w:r><w:r><w:t>{email[4:]}"
    repo = _repo_temporario(tmp_path, {"cnpj.docx": _docx(partido), "email.docx": _docx(email_partido),
                                       "limpo.docx": _docx("nada</w:t></w:r><w:r><w:t> aqui")})
    _git(repo, "add", ".")
    r = _rodar(repo)
    assert r.returncode == 1
    assert "cnpj.docx!word/document.xml:1: CNPJ valido" in r.stdout
    assert "email.docx!word/document.xml:1: e-mail real" in r.stdout
    assert "limpo.docx" not in r.stdout and cnpj not in r.stdout and "fulano" not in r.stdout


def test_docx_com_mailto_no_rels_e_achado_no_xml_cru():
    rels = f'<Relationship Id="r1" Target="mailto:fulano@{DOM_GRUPO_COM}" TargetMode="External"/>'
    dados = _docx("nada", {"word/_rels/document.xml.rels": rels})
    achados = []
    for sub, texto, _motivo in vazamento.conteudos("a.docx", dados):
        achados += vazamento.varrer(sub, texto, vazamento.Excecoes())
    assert [(a[0], a[2]) for a in achados] == [("a.docx!word/_rels/document.xml.rels", "e-mail real")]


def test_xml_grande_demais_dentro_do_office_falha_em_vez_de_passar_em_silencio():
    dados = _docx("nada", {"xl/sharedStrings.xml": "a" * (vazamento.LIMITE_BYTES + 1)})
    itens = list(vazamento.conteudos("a.xlsx", dados))
    assert ("a.xlsx!xl/sharedStrings.xml", None, "arquivo grande demais para varrer") in itens


def test_base_tambem_falha_quando_a_pr_altera_o_script_ou_um_hook_que_ja_existia(tmp_path):
    repo, _cnpj = _repo_com_base(tmp_path, lista_na_base=True)
    (repo / ".githooks").mkdir()
    (repo / ".githooks" / "pre-push").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "hook na base")
    _git(repo, "branch", "-f", "master", "HEAD")
    assert _rodar(repo, "--base", "master").returncode == 0                  # nada mudou

    (repo / "scripts" / "vazamento.py").write_text(
        (repo / "scripts" / "vazamento.py").read_text(encoding="utf-8") + "\n# editado\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "mexe no script")
    r = _rodar(repo, "--base", "master")
    assert r.returncode == 1 and "scripts/vazamento.py" in r.stderr and "exige merge do Leo" in r.stderr

    _git(repo, "checkout", "-q", "master")
    _git(repo, "checkout", "-q", "-b", "pr2")
    (repo / ".githooks" / "pre-push").write_text("#!/bin/sh\nexit 0 # editado\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "mexe no hook")
    r = _rodar(repo, "--base", "master")
    assert r.returncode == 1 and ".githooks/pre-push" in r.stderr

    _git(repo, "checkout", "-q", "master")
    _git(repo, "checkout", "-q", "-b", "pr3")
    (repo / ".githooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")  # hook NOVO: nao conta
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "hook novo")
    assert _rodar(repo, "--base", "master").returncode == 0


def test_base_varre_cada_commit_da_pr_mesmo_que_o_seguinte_tire_o_dado(tmp_path):
    cnpj = formatado(cnpj_valido_inventado())
    repo, _ = _repo_com_base(tmp_path, lista_na_base=False)
    (repo / "vazou.txt").write_text(f"CNPJ {cnpj}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "poe o dado")
    _git(repo, "rm", "-q", "vazou.txt")
    _git(repo, "commit", "-q", "-m", "tira o dado")
    r = _rodar(repo, "--base", "master")                 # a arvore final esta' limpa, o historico da PR nao
    assert r.returncode == 1 and "vazou.txt@" in r.stdout and "CNPJ valido" in r.stdout and cnpj not in r.stdout


ZERO = "0" * 40


def _repo_de_push(tmp_path):
    """Repositorio com a base limpa; devolve (repo, sha da base)."""
    repo = _repo_temporario(tmp_path, {"limpo.txt": "ok\n"})
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    return repo, _git_saida(repo, "rev-parse", "HEAD")


def _push(repo, ref_local, sha_local, ref_remota="refs/heads/x", sha_remoto=ZERO):
    return _rodar(repo, "--push", entrada=f"{ref_local} {sha_local} {ref_remota} {sha_remoto}\n")


def test_push_barra_commit_com_dado_apagado_so_no_disco(tmp_path):
    repo, _base = _repo_de_push(tmp_path)
    cnpj = formatado(cnpj_valido_inventado())
    (repo / "vazou.txt").write_text(f"CNPJ {cnpj}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "dado furando o pre-commit")
    (repo / "vazou.txt").write_text("limpo no disco\n", encoding="utf-8")        # nao commitado
    sha = _git_saida(repo, "rev-parse", "HEAD")
    r = _push(repo, "refs/heads/x", sha)
    assert r.returncode == 1 and "vazou.txt@" + sha[:8] in r.stdout and cnpj not in r.stdout


def test_push_de_sha_para_outra_ref_e_commit_que_poe_e_o_seguinte_que_tira_tambem_sao_barrados(tmp_path):
    repo, base = _repo_de_push(tmp_path)
    cnpj = formatado(cnpj_valido_inventado())
    (repo / "vazou.txt").write_text(f"CNPJ {cnpj}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "poe")
    poe = _git_saida(repo, "rev-parse", "HEAD")
    _git(repo, "rm", "-q", "vazou.txt")
    _git(repo, "commit", "-q", "-m", "tira")
    tira = _git_saida(repo, "rev-parse", "HEAD")
    # `git push origin <sha>:refs/heads/outra`: a ref local e' o proprio sha
    assert _push(repo, tira, tira, "refs/heads/outra").returncode == 1
    # remoto ja' tem a base: so' os commits depois dela, e o primeiro tem o dado
    assert _push(repo, "refs/heads/x", tira, sha_remoto=base).returncode == 1
    # remoto desconhecido para este repositorio: conta o que nenhum remoto tem
    assert _push(repo, "refs/heads/x", tira, sha_remoto="1" * 40).returncode == 1
    # o remoto ja' tem o commit que tirou o dado (e o que pos): nada a enviar
    assert _push(repo, "refs/heads/x", tira, sha_remoto=tira).returncode == 0
    # so' o commit que tirou
    assert _push(repo, "refs/heads/x", tira, sha_remoto=poe).returncode == 0


def test_push_limpo_e_apagar_ref_passam(tmp_path):
    repo, base = _repo_de_push(tmp_path)
    (repo / "outro.txt").write_text("nada\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "limpo")
    sha = _git_saida(repo, "rev-parse", "HEAD")
    assert _push(repo, "refs/heads/x", sha, sha_remoto=base).returncode == 0
    assert _push(repo, "(delete)", ZERO, sha_remoto=sha).returncode == 0
    assert _rodar(repo, "--push", entrada="").returncode == 0


def _commit(repo, arquivo, texto, msg):
    (repo / arquivo).write_text(texto, encoding="utf-8")
    _git(repo, "add", arquivo)
    _git(repo, "commit", "-q", "--no-verify", "-m", msg)
    return _git_saida(repo, "rev-parse", "HEAD")


def _repo_com_master_e_feat(tmp_path, texto_master, texto_feat):
    """Base limpa; `master` ganha um commit (publicado: a ref remota aponta para ele) e a `feat` parte da base com
    outro commit. Devolve (repo, sha do master, sha da feat)."""
    repo, base = _repo_de_push(tmp_path)
    arquivo_master, conteudo_master = texto_master
    master = _commit(repo, arquivo_master, conteudo_master, "master muda")
    _git(repo, "update-ref", "refs/remotes/origin/master", master)
    _git(repo, "checkout", "-q", "-b", "feat", base)
    arquivo_feat, conteudo_feat = texto_feat
    feat = _commit(repo, arquivo_feat, conteudo_feat, "feat")
    return repo, master, feat


def test_push_com_merge_de_master_nao_barra_dado_antigo_que_o_remoto_ja_tem(tmp_path):
    cnpj = formatado(cnpj_valido_inventado())
    repo, master, feat = _repo_com_master_e_feat(tmp_path, ("antigo.txt", f"CNPJ {cnpj}\n"), ("feat.txt", "ok\n"))
    _git(repo, "merge", "-q", "--no-edit", master)               # merge sem conflito traz o commit antigo do master
    tip = _git_saida(repo, "rev-parse", "HEAD")
    assert _push(repo, "refs/heads/feat", tip, sha_remoto=feat).returncode == 0
    # ref da feat nova no remoto: tambem so' o que nenhum remoto tem
    assert _push(repo, "refs/heads/feat", tip).returncode == 0


def _merge_com_conflito(repo, master, resolucao):
    """Merge do master na feat com conflito em limpo.txt, resolvido com `resolucao`; devolve o sha do merge."""
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "merge", "--no-edit", master],
                       cwd=repo, capture_output=True, text=True, check=False)
    assert r.returncode != 0, "esperava conflito"
    (repo / "limpo.txt").write_text(resolucao, encoding="utf-8")
    _git(repo, "add", "limpo.txt")
    _git(repo, "commit", "-q", "--no-verify", "--no-edit")
    return _git_saida(repo, "rev-parse", "HEAD")


def test_push_barra_dado_novo_na_resolucao_de_conflito_de_um_merge(tmp_path):
    cnpj = formatado(cnpj_valido_inventado())
    repo, master, feat = _repo_com_master_e_feat(tmp_path, ("limpo.txt", "versao do master\n"),
                                                 ("limpo.txt", "versao da feat\n"))
    tip = _merge_com_conflito(repo, master, f"resolvido com CNPJ {cnpj}\n")
    r = _push(repo, "refs/heads/feat", tip, sha_remoto=feat)
    assert r.returncode == 1 and f"limpo.txt@{tip[:8]}:1: CNPJ valido" in r.stdout and cnpj not in r.stdout


def test_push_deixa_passar_conflito_de_merge_resolvido_sem_dado(tmp_path):
    repo, master, feat = _repo_com_master_e_feat(tmp_path, ("limpo.txt", "versao do master\n"),
                                                 ("limpo.txt", "versao da feat\n"))
    tip = _merge_com_conflito(repo, master, "resolvido sem dado\n")
    assert _push(repo, "refs/heads/feat", tip, sha_remoto=feat).returncode == 0


def test_arvore_atual_do_repositorio_esta_limpa(monkeypatch):
    """Criterio da issue #106: `python scripts/vazamento.py` termina com 0 (a lista de nomes e' local: fica de fora).
    Falha no master ate' a #110 tirar o dado real que sobrou (CNPJs e e-mails nas migracoes e no codigo)."""
    monkeypatch.delenv("DASH_SERVIDOR", raising=False)
    monkeypatch.setattr(vazamento, "caminhos_nomes", lambda: [])
    assert vazamento.main([]) == 0
