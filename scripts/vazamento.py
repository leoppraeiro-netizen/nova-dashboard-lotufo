"""Barra dado real no repositorio publico (issue #106).

Percorre os arquivos versionados (`git ls-files`) e falha (codigo 1) se achar:
  - CNPJ ou CPF com digito verificador valido fora de `scripts/vazamento-excecoes.txt` (o CNPJ vale com separador
    irregular: so' barra e hifen, espacos, NBSP; tambem o CNPJ alfanumerico com pontuacao);
  - e-mail de `lotufoengenharia.com.br`, `grupolotufo.*`, qualquer dominio com "lotufo" que nao seja `lotufo.com`,
    `mt.gov.br` ou qualquer `.gov.br` que nao seja `@exemplo.gov.br`;
  - chave de acesso de NFS-e (50 digitos) ou de NF-e (44), junta ou em grupos de 4, e o CNPJ do emissor dentro dela;
  - o nome da maquina de producao, vindo de `DASH_SERVIDOR` (na CI, de um secret; nos hooks, do COMPUTERNAME);
    sem ele a checagem e' pulada com aviso;
  - termo de `scripts/vazamento-nomes.txt` (nomes de pessoas; o arquivo e' local, esta no .gitignore, e na CI a
    parte e' pulada porque ele nao existe la'); sem acento, sem diferenca de caixa e com `.`, `_`, `-` ou espaco
    entre as palavras;
  - binario fora da lista permitida (`.docx`/`.xlsx`/`.pptx` sao abertos e o texto de dentro e' varrido).

A saida traz arquivo, linha e o trecho com o dado MASCARADO (`01.318.***`): o log da CI e' publico.

Uso:
  python scripts/vazamento.py                   # todos os arquivos de `git ls-files`
  python scripts/vazamento.py --staged          # so' os arquivos do commit, lidos do indice (pre-commit)
  python scripts/vazamento.py --push < refs     # commits que o push envia, um a um (pre-push le o stdin do git)
  python scripts/vazamento.py --base origin/master   # CI da PR: arvore + cada commit da PR + arquivos protegidos

So' biblioteca padrao. Codigos de saida: 0 limpo, 1 achou dado, 2 erro de uso ou de arquivo de lista.
"""
import argparse
import html
import io
import os
import re
import subprocess
import sys
import unicodedata
import zipfile
from functools import cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ_EXCECOES = Path(__file__).resolve().parent / "vazamento-excecoes.txt"
ARQ_NOMES = Path(__file__).resolve().parent / "vazamento-nomes.txt"
LIMITE_BYTES = 5_000_000


DOMINIO_FICTICIO = "exemplo.gov.br"
DOMINIO_LOTUFO_FICTICIO = "lotufo.com"
# Dominios de e-mail que nao podem aparecer (o proprio dominio e qualquer subdominio dele). Alem destes, vale
# qualquer dominio com "lotufo" que nao seja o fictício e qualquer `.gov.br` que nao seja o fictício.
DOMINIOS_PROIBIDOS = ("lotufoengenharia.com.br", "grupolotufo.com.br", "grupolotufo.srv.br", "mt.gov.br",
                      "cuiaba.mt.gov.br")
SUFIXO_GOV = "gov.br"

# Binarios aceitos sem leitura (imagens e fontes da interface); PDF so' nas fixtures de teste. Office (zip) e' aberto.
BINARIOS_PERMITIDOS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf"})
PDF_SO_EM = "backend/tests/fixtures/"
ZIPS_OFFICE = frozenset({".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm"})

# CNPJs de exemplo de geradores publicos (nao sao de ninguem); os demais CNPJs da lista de excecoes precisam ter
# raiz ficticia 31.2xx / 31.3xx (as de backend/tests/ficticios.py).
CNPJS_DE_EXEMPLO = frozenset({"11444777000161", "12345678000195", "98765432000198"})
RAIZES_FICTICIAS = ("312", "313")

SEP = r"[\s. /-]?"
RE_CNPJ = re.compile(rf"(?<!\d)\d{{2}}{SEP}\d{{3}}{SEP}\d{{3}}{SEP}\d{{4}}{SEP}\d{{2}}(?!\d)")
# CNPJ alfanumerico (Receita, 2026): so' com a pontuacao completa, para nao confundir com identificador qualquer.
RE_CNPJ_ALFA = re.compile(r"(?<![0-9A-Za-z])[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-\d{2}(?!\d)")
# CPF: ponto, espaco ou NBSP entre os grupos e, antes dos 2 digitos finais, tambem hifen (`123456789-00`). Hifen e
# barra entre os grupos nao entram: casariam com data e hora (`163-20260904`) e o digito verificador sozinho
# deixa passar 1 em cada 100.
RE_CPF = re.compile(r"(?<!\d)\d{3}[\s. ]?\d{3}[\s. ]?\d{3}[\s. -]?\d{2}(?!\d)")
RE_CHAVE = re.compile(r"(?<!\d)(?:\d{50}|\d{44}|\d{4}(?:[  ]\d{4}){10,11}(?:[  ]\d{2})?)(?!\d)")
# e-mail, `@dominio` sem nada antes e a forma codificada de URL (`nome%40dominio`)
RE_EMAIL = re.compile(r"([A-Za-z0-9._+-]*)(?:@|%40)([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def normalizar_cnpj(texto: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", texto.upper())


def cnpj_valido(caracteres: str) -> bool:
    """`caracteres` = os 14 sem pontuacao (12 de letras ou numeros + 2 digitos verificadores)."""
    if not re.fullmatch(r"[0-9A-Z]{12}\d{2}", caracteres) or len(set(caracteres)) == 1:
        return False
    nums = [ord(d) - 48 for d in caracteres]
    for tam, pesos in ((12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]), (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])):
        resto = sum(n * p for n, p in zip(nums[:tam], pesos)) % 11
        if nums[tam] != (0 if resto < 2 else 11 - resto):
            return False
    return True


def cpf_valido(digitos: str) -> bool:
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    nums = [int(d) for d in digitos]
    for tam in (9, 10):
        resto = sum(n * p for n, p in zip(nums[:tam], range(tam + 1, 1, -1))) * 10 % 11
        if nums[tam] != (0 if resto == 10 else resto):
            return False
    return True


def cnpj_da_chave(digitos: str) -> str:
    """CNPJ do emissor dentro da chave: NFS-e (50) na posicao 9, NF-e (44) na posicao 6."""
    return digitos[9:23] if len(digitos) == 50 else digitos[6:20]


def mascarar(dado: str, mostrar: int = 6) -> str:
    """Mostra so' o comeco (`01.318.***`, como pede a issue para CNPJ); nunca o dado inteiro."""
    return dado[:min(mostrar, max(len(dado) - 1, 0))] + "***"


def sem_acento(texto: str) -> str:
    """Tira o acento caractere a caractere, mantendo o tamanho (os indices continuam valendo no texto original)."""
    return "".join(unicodedata.normalize("NFKD", c)[0] for c in texto)


class Excecoes:
    """Valores aceitos. Uma entrada por linha, `#` comenta.

    - CNPJ, CPF e chave de NFS-e/NF-e ficticios valem em qualquer formatacao (comparados so' pelos digitos);
      CNPJ em claro so' com raiz ficticia (31.2xx / 31.3xx);
    - e-mail inteiro ou `@dominio` aceitam o e-mail / todos do dominio.
    Dado REAL nunca entra aqui. Mudar a lista exige merge do Leo (o job `vazamento` falha na PR que a altera).
    """

    def __init__(self, documentos=(), emails=(), dominios=()):
        self.documentos = set(documentos) | CNPJS_DE_EXEMPLO
        self.emails = {e.lower() for e in emails}
        self.dominios = {d.lower() for d in dominios}

    @classmethod
    def de_texto(cls, texto: str, origem: str = "vazamento-excecoes.txt") -> "Excecoes":
        exc = cls()
        for n, bruta in enumerate(texto.splitlines(), 1):
            linha = bruta.split("#", 1)[0].strip()
            if not linha:
                continue
            digitos = so_digitos(linha)
            if "@" in linha:
                (exc.dominios if linha.startswith("@") else exc.emails).add(linha.lstrip("@").lower())
            elif len(digitos) in (11, 14, 44, 50) and re.fullmatch(r"[\d./\- ]+", linha):
                if len(digitos) == 14 and digitos not in CNPJS_DE_EXEMPLO and not digitos.startswith(
                        RAIZES_FICTICIAS):
                    raise ValueError(f"{origem}:{n}: CNPJ em claro so' com raiz ficticia (31.2xx ou 31.3xx)")
                exc.documentos.add(digitos)
            else:
                raise ValueError(f"{origem}:{n}: entrada nao reconhecida (CNPJ, CPF, chave de 44 ou 50 digitos, "
                                 "e-mail ou @dominio)")
        return exc

    @classmethod
    def ler(cls, caminho: Path) -> "Excecoes":
        if not caminho.exists():
            return cls()
        return cls.de_texto(caminho.read_text(encoding="utf-8"), caminho.name)

    def libera_documento(self, digitos: str) -> bool:
        return digitos in self.documentos

    def libera_email(self, email: str, dominio: str) -> bool:
        return email.lower() in self.emails or dominio.lower() in self.dominios


def caminhos_nomes() -> list:
    """Onde procurar a lista local: ao lado do script e na pasta principal do repositorio. Num worktree do Claude o
    arquivo (gitignorado) so' existe na pasta principal; `--git-common-dir` aponta para o `.git` dela."""
    caminhos = [ARQ_NOMES]
    try:
        comum = _git("rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()
        caminhos.append(Path(comum).parent / "scripts" / ARQ_NOMES.name)
    except (OSError, subprocess.CalledProcessError):
        pass
    return caminhos


def ler_termos(caminhos) -> list:
    """Lista de nomes de pessoas, um por linha. Ausente (como na CI) devolve vazio."""
    termos = []
    for caminho in caminhos:
        if not caminho.exists():
            continue
        for bruta in caminho.read_text(encoding="utf-8").splitlines():
            termo = bruta.split("#", 1)[0].strip()
            if termo and termo not in termos:
                termos.append(termo)
    return termos


def _dominio_proibido(dominio: str) -> bool:
    dominio = dominio.lower().rstrip(".")
    if dominio in (DOMINIO_FICTICIO, DOMINIO_LOTUFO_FICTICIO):
        return False
    if "lotufo" in dominio:
        return True
    for d in DOMINIOS_PROIBIDOS + (SUFIXO_GOV,):
        if dominio == d or dominio.endswith("." + d):
            return True
    return False


@cache
def _termo(termo: str):
    """Palavras do termo unidas por espaco, `.`, `_` ou `-`, sem acento e sem diferenca de caixa."""
    palavras = [p for p in re.split(r"[\s._-]+", sem_acento(termo).strip()) if p]
    return re.compile(r"(?<![A-Za-z0-9])" + r"[\s._-]+".join(map(re.escape, palavras)) + r"(?![A-Za-z0-9])",
                      re.IGNORECASE)


def achar(texto: str, excecoes: Excecoes, termos=(), servidores=()) -> list:
    """Achados de UMA linha: lista de (inicio, fim, tipo, mascara), sem sobreposicao.

    O que as excecoes liberam entra com `tipo` None: nao e' relatado, mas o trecho impresso o mascara tambem.
    """
    achados = []

    def aceita(inicio, fim, tipo, mascara):
        achados.append((inicio, fim, tipo, mascara))

    for m in RE_CHAVE.finditer(texto):
        d = so_digitos(m.group())
        if len(d) not in (44, 50):
            continue
        tipo_chave = "chave de acesso de NFS-e" if len(d) == 50 else "chave de acesso de NF-e"
        aceita(m.start(), m.end(), None if excecoes.libera_documento(d) else tipo_chave, mascarar(m.group(), 4))
        emissor = cnpj_da_chave(d)
        if cnpj_valido(emissor):
            liberado = excecoes.libera_documento(emissor)
            aceita(m.start(), m.end(), None if liberado else "CNPJ valido (emissor da chave)", mascarar(m.group(), 4))
    for regex in (RE_CNPJ, RE_CNPJ_ALFA):
        for m in regex.finditer(texto):
            c = normalizar_cnpj(m.group())
            if cnpj_valido(c):
                liberado = excecoes.libera_documento(c)
                aceita(m.start(), m.end(), None if liberado else "CNPJ valido",
                       mascarar(m.group(), 7 if "." in m.group() else 6))
    for m in RE_CPF.finditer(texto):
        d = so_digitos(m.group())
        if cpf_valido(d):
            liberado = excecoes.libera_documento(d)
            aceita(m.start(), m.end(), None if liberado else "CPF valido", mascarar(m.group(), 3))
    for m in RE_EMAIL.finditer(texto):
        local, dominio = m.group(1), m.group(2).lower()
        if _dominio_proibido(dominio):
            liberado = excecoes.libera_email(f"{local}@{dominio}", dominio)
            aceita(m.start(), m.end(), None if liberado else "e-mail real", local[:2] + "***@" + m.group(2))
    if servidores or termos:
        normal = sem_acento(texto)
        for servidor in servidores:
            for m in _termo(servidor).finditer(normal):
                aceita(m.start(), m.end(), "nome da maquina de producao", mascarar(texto[m.start():m.end()], 2))
        for termo in termos:
            for m in _termo(termo).finditer(normal):
                aceita(m.start(), m.end(), "nome de pessoa da lista local", mascarar(texto[m.start():m.end()], 2))

    # sem sobreposicao: o mais comprido primeiro; em empate, o que sera' relatado antes do silencioso
    achados.sort(key=lambda a: (a[0], -(a[1] - a[0]), a[2] is None))
    limpos, fim_anterior = [], 0
    for a in achados:
        if a[0] >= fim_anterior:
            limpos.append(a)
            fim_anterior = a[1]
    return limpos


def trecho(linha: str, achados: list, i: int, folga: int = 25) -> str:
    """Janela em volta do achado `i`, com TODOS os achados da linha trocados pela mascara."""
    pedacos, pos, inicio_mascarado = [], 0, 0
    for k, (ini, fim, _tipo, mascara) in enumerate(achados):
        pedacos.append(linha[pos:ini])
        if k == i:
            inicio_mascarado = sum(len(p) for p in pedacos)
        pedacos.append(mascara)
        pos = fim
    pedacos.append(linha[pos:])
    mascarada = "".join(pedacos)
    fim_mascarado = inicio_mascarado + len(achados[i][3])
    return mascarada[max(0, inicio_mascarado - folga):fim_mascarado + folga].strip()


def varrer(nome: str, conteudo: str, excecoes: Excecoes, termos=(), servidores=()) -> list:
    """Achados de um arquivo: lista de (arquivo, linha, tipo, trecho mascarado)."""
    saida = []
    for numero, linha in enumerate(conteudo.splitlines(), 1):
        achados = achar(linha, excecoes, termos, servidores)
        for i, (_ini, _fim, tipo, _mascara) in enumerate(achados):
            if tipo is None:
                continue
            saida.append((nome, numero, tipo, trecho(linha, achados, i)))
    return saida


def texto_do_xml(xml: str) -> str:
    """Texto corrido de um XML do Office: o Word parte o texto em varios `<w:t>`, entao as marcacoes saem (fim de
    paragrafo vira quebra de linha) e as entidades voltam a ser caracteres."""
    xml = re.sub(r"</(?:w:p|a:p|si)>|<w:br\s*/>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def _parte_de_texto_corrido(caminho: str) -> bool:
    if caminho.endswith(".rels"):
        return False
    return caminho.startswith(("word/", "ppt/")) or caminho == "xl/sharedStrings.xml"


def conteudos(nome: str, dados: bytes):
    """Textos a varrer de um arquivo: itens (nome, texto, None). Um item (nome, None, motivo) e' arquivo que a
    varredura nao consegue ler e que, por isso, falha em vez de passar em silencio."""
    ext = Path(nome).suffix.lower()
    if ext in ZIPS_OFFICE:
        try:
            zf = zipfile.ZipFile(io.BytesIO(dados))
        except zipfile.BadZipFile:
            yield nome, None, "arquivo Office ilegivel"
            return
        for info in zf.infolist():
            if not info.filename.lower().endswith((".xml", ".rels")):
                continue
            sub = f"{nome}!{info.filename}"
            if info.file_size > LIMITE_BYTES:
                yield sub, None, "arquivo grande demais para varrer"
                continue
            xml = zf.read(info).decode("utf-8", errors="replace")
            # texto de word/ e ppt/ e as strings da planilha sem marcacao; o resto (.rels com `mailto:`, propriedades
            # do documento) no XML cru
            yield sub, texto_do_xml(xml) if _parte_de_texto_corrido(info.filename) else xml, None
        return
    if ext in BINARIOS_PERMITIDOS or (ext == ".pdf" and nome.startswith(PDF_SO_EM)):
        return
    if b"\0" in dados[:8000]:
        yield nome, None, f"binario fora da lista permitida ({ext or 'sem extensao'})"
    elif len(dados) > LIMITE_BYTES:
        yield nome, None, "arquivo grande demais para varrer"
    else:
        yield nome, dados.decode("utf-8", errors="replace"), None


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=RAIZ, check=True, capture_output=True).stdout


def arquivos_alvo(staged: bool) -> list:
    if staged:
        bruto = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    else:
        bruto = _git("ls-files", "-z")
    return [n for n in bruto.decode("utf-8").split("\0") if n]


def ler_bytes(nome: str, staged: bool):
    """Bytes do arquivo (do indice no pre-commit, do disco nos demais); None se sumiu."""
    try:
        return _git("show", ":" + nome) if staged else (RAIZ / nome).read_bytes()
    except (OSError, subprocess.CalledProcessError):
        return None


def excecoes_do_modo(staged: bool) -> Excecoes:
    """No pre-commit a lista vem do indice (o que vai no commit), nao do disco."""
    rel = ARQ_EXCECOES.relative_to(RAIZ).as_posix()
    if staged:
        dados = ler_bytes(rel, True)
        return Excecoes.de_texto(dados.decode("utf-8"), ARQ_EXCECOES.name) if dados is not None else Excecoes()
    return Excecoes.ler(ARQ_EXCECOES)


def excecoes_de_ref(ref: str) -> Excecoes:
    """Lista de excecoes como esta' commitada em `ref` (vazia se nao existe la')."""
    rel = ARQ_EXCECOES.relative_to(RAIZ).as_posix()
    try:
        return Excecoes.de_texto(_git("show", f"{ref}:{rel}").decode("utf-8"), ARQ_EXCECOES.name)
    except subprocess.CalledProcessError:
        return Excecoes()


def protegidos_alterados(base: str) -> list:
    """Arquivos que decidem o que passa (o proprio script, a lista de excecoes e os hooks) e que a branch altera ou
    apaga em relacao a `base`. Arquivo novo nao conta: a primeira PR que o cria nao se bloqueia."""
    protegidos = [p.relative_to(RAIZ).as_posix() for p in (Path(__file__).resolve(), ARQ_EXCECOES)] + [".githooks"]
    saida = _git("diff", "--name-only", "--no-renames", "--diff-filter=MDT", f"{base}...HEAD", "--", *protegidos)
    return saida.decode("utf-8").split()


ZEROS = "0" * 40


def revs_do_push(linhas) -> list:
    """Do stdin do pre-push (`<ref local> <sha local> <ref remoto> <sha remoto>`) tira, por ref, os argumentos do
    `git rev-list` com os commits que o push envia: so' o que nem o remoto da ref nem nenhum outro remoto ja' tem
    (um merge de master traz commits antigos que nao sao do autor do push). Ref apagada nao envia nada."""
    revs = []
    for linha in linhas:
        partes = linha.split()
        if len(partes) < 4 or set(partes[1]) == {"0"}:
            continue
        local, remoto = partes[1], partes[3]
        conhecido = set(remoto) != {"0"} and subprocess.run(
            ["git", "cat-file", "-e", remoto + "^{commit}"], cwd=RAIZ, capture_output=True, check=False
        ).returncode == 0
        revs.append([local, "--not", *([remoto] if conhecido else []), "--remotes"])
    return revs


def achados_dos_commits(revs: list, excecoes: Excecoes, termos, servidores) -> list:
    """Varre, commit a commit, os arquivos que cada um tocou, na versao daquele commit: dado que entrou num commit e
    saiu no seguinte continua no historico publicado. Num commit de merge so' entram os arquivos que diferem dos dois
    pais (`--cc`: resolucao de conflito); o resto do merge e' de commits que ja' sao varridos ou ja' estao no remoto."""
    achados = []
    for rev in revs:
        linhas = _git("rev-list", "--parents", "--reverse", *rev).decode().splitlines()
        for linha in linhas:
            sha, *pais = linha.split()
            if len(pais) > 1:
                comando = ["diff-tree", "--cc", "-r", "--no-commit-id", "--name-only", "-z", sha]
            else:
                comando = ["diff-tree", "--root", "-r", "--no-renames", "--no-commit-id", "--diff-filter=ACMRT",
                           "--name-only", "-z", sha]
            nomes = _git(*comando).decode("utf-8").split("\0")
            for nome in (n for n in nomes if n):
                try:
                    dados = _git("show", f"{sha}:{nome}")
                except subprocess.CalledProcessError:
                    continue
                achados += _achados_do_arquivo(f"{nome}@{sha[:8]}", nome, dados, excecoes, termos, servidores)
    return achados


def _achados_do_arquivo(rotulo: str, nome: str, dados: bytes, excecoes, termos, servidores) -> list:
    achados = []
    for sub, texto, motivo in conteudos(nome, dados):
        sub = rotulo + sub[len(nome):]
        if texto is None:
            achados.append((sub, 0, motivo, ""))
        else:
            achados += varrer(sub, texto, excecoes, termos, servidores)
    return achados


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--staged", action="store_true", help="so' os arquivos do commit (pre-commit)")
    ap.add_argument("--push", action="store_true",
                    help="le do stdin as refs do pre-push e varre os commits que o push envia")
    ap.add_argument("--base", metavar="REF",
                    help="CI da PR: alem da arvore, varre cada commit de REF..HEAD e falha se a PR altera os "
                         "arquivos protegidos (script, lista de excecoes, hooks)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        excecoes = excecoes_de_ref("HEAD") if args.push else excecoes_do_modo(args.staged)
    except ValueError as erro:
        print(f"vazamento: {erro}", file=sys.stderr)
        return 2
    termos = ler_termos(caminhos_nomes())
    if not termos:
        print("vazamento: sem scripts/vazamento-nomes.txt, lista de nomes de pessoas pulada", file=sys.stderr)
    servidor = os.environ.get("DASH_SERVIDOR", "").strip()
    if not servidor:
        print("vazamento: sem DASH_SERVIDOR, checagem do nome da maquina pulada", file=sys.stderr)
    servidores = {servidor} if servidor else set()

    achados = []
    try:
        if args.push:
            achados += achados_dos_commits(revs_do_push(sys.stdin), excecoes, termos, servidores)
        else:
            for nome in arquivos_alvo(args.staged):
                dados = ler_bytes(nome, args.staged)
                if dados is not None:
                    achados += _achados_do_arquivo(nome, nome, dados, excecoes, termos, servidores)
            if args.base:
                achados += achados_dos_commits([[f"{args.base}..HEAD"]], excecoes, termos, servidores)
    except subprocess.CalledProcessError as erro:
        print(f"vazamento: git falhou ({' '.join(map(str, erro.cmd[:4]))}...)", file=sys.stderr)
        return 2
    for arquivo, linha, tipo, pedaco in achados:
        print(f"{arquivo}:{linha}: {tipo}: ...{pedaco}..." if linha else f"{arquivo}: {tipo}")
    status = 0
    if achados:
        print(f"vazamento: {len(achados)} achado(s). Troque por dado ficticio; se for ficticio de proposito, "
              "ponha na lista scripts/vazamento-excecoes.txt (mudanca na lista exige merge do Leo).",
              file=sys.stderr)
        status = 1
    if args.base:
        try:
            mudaram = protegidos_alterados(args.base)
        except subprocess.CalledProcessError:
            print(f"vazamento: nao consegui comparar com {args.base}", file=sys.stderr)
            return 2
        if mudaram:
            print("vazamento: esta PR altera " + ", ".join(mudaram) + ". Mudanca no script, na lista de excecoes "
                  "ou nos hooks exige merge do Leo.", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
