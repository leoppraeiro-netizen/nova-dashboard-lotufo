"""Corpo de e-mail formatado na tela (issue #191): lista FECHADA de tags e estilos.

O editor do e-mail (ComporEmail) manda o corpo em HTML quando a pessoa mexe nele; o texto pre-montado que ninguem
tocou continua chegando em texto puro e cada modulo o converte como sempre. Do HTML so' passa:
b/strong, i/em, u, s, p, br, ul, ol, li e span com `color` e `background-color` (cor simples). Todo o resto sai:
atributo, evento, imagem, link, tabela, fonte, tamanho. Tag fora da lista some e o texto dela fica; script, style,
head e afins somem com o conteudo. `<div>` (uma linha do editor) vira quebra de linha. So' biblioteca padrao.
"""
import html
import re
from html.parser import HTMLParser

_PERMITIDAS = {"b": "b", "strong": "strong", "i": "i", "em": "em", "u": "u", "s": "s", "strike": "s", "del": "s",
               "p": "p", "ul": "ul", "ol": "ol", "li": "li", "span": "span", "font": "span"}
_BLOCOS = {"p", "ul", "ol", "li"}
# tags que viram uma linha (o editor do navegador poe cada linha num <div>)
_LINHAS = {"div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "address", "center", "section",
           "article", "header", "footer", "tr", "dt", "dd", "table"}
# somem com tudo o que tem dentro
_SEM_CONTEUDO = {"script", "style", "head", "title", "iframe", "object", "embed", "noscript", "template", "svg",
                 "math", "xml", "textarea", "select", "button", "frameset", "noembed", "noframes", "applet"}
_VAZIAS = {"br", "img", "hr", "meta", "link", "input", "wbr", "col", "area", "base", "source", "track", "param"}
_COR = re.compile(r"(#[0-9a-f]{3}|#[0-9a-f]{6}|rgba?\(\s*\d{1,3}%?\s*(,\s*\d{1,3}%?\s*){2}(,\s*(0|1|0?\.\d+)\s*)?\)"
                  r"|[a-z]{3,20})", re.I)
_URL = re.compile(r"https://[^\s<>\"]+")
# so' as tags que o editor da tela produz: texto puro com "<nota>" ou "a < b" continua texto e e' escapado como
# sempre; HTML sem nenhuma delas (so' <script>, p.ex.) tambem cai no texto puro e sai escapado, inofensivo
_TAG = re.compile(r"</?(div|p|br|b|strong|i|em|u|s|strike|span|font|ul|ol|li)(\s[^<>]*)?/?>", re.I)


def eh_html(corpo: str) -> bool:
    """O corpo veio do editor (tem alguma tag que o editor produz)?"""
    return bool(_TAG.search(corpo or ""))


def _estilo(style: str | None) -> str | None:
    cores = {}
    for parte in (style or "").split(";"):
        nome, _, valor = parte.partition(":")
        nome, valor = nome.strip().lower(), valor.strip()
        if nome == "background":
            nome = "background-color"            # o Word marca o realce como `background:yellow`
        if nome in ("color", "background-color") and _COR.fullmatch(valor):
            cores[nome] = valor
    return "; ".join(f"{k}: {v}" for k, v in cores.items()) or None


class _Limpador(HTMLParser):
    def __init__(self, links: bool):
        super().__init__(convert_charrefs=True)
        self.links, self.saida, self.pilha, self.pular = links, [], [], 0
        self.ultimo = "nada"              # "texto": ha' conteudo na linha aberta; "quebra"/"bloco": linha fechada

    def _emitir(self, s: str, ultimo: str) -> None:
        self.saida.append(s)
        self.ultimo = ultimo

    def handle_starttag(self, tag, attrs):
        if self.pular:
            if tag in _SEM_CONTEUDO:
                self.pular += 1
            return
        if tag in _SEM_CONTEUDO:
            self.pular = 1
            return
        if tag == "br":
            self._emitir("<br>", "quebra")
            return
        if tag in _LINHAS:
            if self.ultimo == "texto":
                self._emitir("<br>", "quebra")
            self.pilha.append((tag, None))
            return
        if tag in _VAZIAS:
            return
        destino = _PERMITIDAS.get(tag)
        if destino == "span":
            a = dict(attrs)
            estilo = _estilo(a.get("style"))
            if tag == "font" and a.get("color") and _COR.fullmatch(a["color"].strip()):
                estilo = _estilo(f"color:{a['color'].strip()};{a.get('style') or ''}")
            if not estilo:
                destino = None
            else:
                self.pilha.append((tag, "span"))
                self.saida.append(f'<span style="{html.escape(estilo)}">')
                return
        if destino is None:
            self.pilha.append((tag, None))        # tag fora da lista: some, o texto fica
            return
        self.pilha.append((tag, destino))
        if destino in _BLOCOS:
            self._emitir(f"<{destino}>", "bloco")
        else:
            self.saida.append(f"<{destino}>")

    def handle_startendtag(self, tag, attrs):
        if tag == "br" or tag in _VAZIAS or tag in _SEM_CONTEUDO:
            if tag == "br" and not self.pular:
                self._emitir("<br>", "quebra")
            return
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.pular:
            if tag in _SEM_CONTEUDO:
                self.pular -= 1
            return
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                while len(self.pilha) > i:
                    self._fechar(*self.pilha.pop())
                return
        # fechamento sem abertura: ignorado

    def _fechar(self, tag, destino):
        if tag in _LINHAS:
            if self.ultimo == "texto":
                self._emitir("<br>", "quebra")
        elif destino in _BLOCOS:
            self._emitir(f"</{destino}>", "bloco")
        elif destino:
            self.saida.append(f"</{destino}>")

    def handle_data(self, data):
        if self.pular or not data:
            return
        t = html.escape(data)
        if self.links:
            t = _URL.sub(lambda m: f'<a href="{m.group(0)}">{m.group(0)}</a>', t)
        self.saida.append(t)
        if data.strip():
            self.ultimo = "texto"

    def fim(self) -> str:
        self.close()
        while self.pilha:
            self._fechar(*self.pilha.pop())
        s = "".join(self.saida)
        while s.endswith("<br>"):
            s = s[:-4]
        return s


def sanitizar(corpo: str, *, links: bool = False) -> str:
    """HTML do editor -> HTML com so' a lista fechada. `links`: endereco https no texto vira link (como o
    protocolo ja' fazia com o texto puro)."""
    p = _Limpador(links)
    p.feed(corpo or "")
    return p.fim()
