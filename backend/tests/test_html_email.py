"""Corpo de e-mail formatado (issue #191): o HTML que vem da tela passa por lista fechada de tags e estilos."""
from app import html_email


def test_texto_puro_nao_e_html_e_html_da_tela_e():
    assert not html_email.eh_html("Bom dia.\n\nSegue a nota.")
    assert not html_email.eh_html("Valor < 10 e > 5")
    assert not html_email.eh_html("Segue a <nota> e o <script>x</script>")
    assert html_email.eh_html("Bom dia<br/>Segue")
    assert html_email.eh_html("Bom dia.<div>Segue</div>")
    assert html_email.eh_html("<b>Bom</b> dia")


def test_lista_fechada_mantem_a_formatacao_do_editor():
    entrada = ('<b>negrito</b> <strong>forte</strong> <i>it</i> <em>en</em> <u>sub</u> <s>riscado</s> '
               '<span style="color: rgb(255, 0, 0);">vermelho</span> '
               '<span style="background-color: #ffff00;">realce</span>'
               '<ul><li>um</li></ul><ol><li>dois</li></ol><p>par</p>')
    assert html_email.sanitizar(entrada) == (
        '<b>negrito</b> <strong>forte</strong> <i>it</i> <em>en</em> <u>sub</u> <s>riscado</s> '
        '<span style="color: rgb(255, 0, 0)">vermelho</span> '
        '<span style="background-color: #ffff00">realce</span>'
        '<ul><li>um</li></ul><ol><li>dois</li></ol><p>par</p>')


def test_html_perigoso_sai_limpo():
    entrada = ('<p onclick="roubar()">oi<script>alert(1)</script></p><img src=x onerror="alert(2)">'
               '<span style="position:fixed;top:0;color:red">x</span>'
               '<span style="color: expression(alert(3))">y</span>'
               '<span style="background-color: url(javascript:alert(4))">z</span>'
               '<a href="javascript:alert(5)">link</a><iframe src="https://x">dentro</iframe>'
               '<style>p{color:red}</style><b class="c" id="i" style="color:red">n</b>')
    saida = html_email.sanitizar(entrada)
    assert saida == '<p>oi</p><span style="color: red">x</span>yzlink<b>n</b>'
    for proibido in ("script", "onclick", "onerror", "img", "position", "expression", "url(", "javascript",
                     "iframe", "dentro", "style>", "class", "id="):
        assert proibido not in saida


def test_texto_e_reescapado():
    assert html_email.sanitizar("<b>a &lt;script&gt; &amp; b</b>") == "<b>a &lt;script&gt; &amp; b</b>"


def test_linhas_do_editor_viram_quebras():
    # o editor do navegador poe cada linha num <div>; linha vazia e' <div><br></div>
    assert html_email.sanitizar("Bom dia,<div><br></div><div>Segue a <b>nota</b>.</div><div>Att.</div>") == \
        "Bom dia,<br><br>Segue a <b>nota</b>.<br>Att."


def test_tabela_colada_vira_uma_linha_por_celula():
    assert html_email.sanitizar("<table><tr><td>Item 1</td><td>R$ 100,00</td></tr>"
                                "<tr><td>Item 2</td><td>R$ 200,00</td></tr></table>") == \
        "Item 1<br>R$ 100,00<br>Item 2<br>R$ 200,00"


def test_colar_do_word_mantem_so_a_lista_fechada():
    word = ('<html xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta charset="utf-8">'
            '<style>@font-face{font-family:Calibri}</style><!--[if gte mso 9]><xml><o:x>1</o:x></xml><![endif]-->'
            '</head><body lang=PT-BR><!--StartFragment-->'
            '<p class=MsoNormal style="margin:0cm;font-size:11pt;font-family:Calibri"><b><span '
            'style="font-size:14.0pt;color:#C00000;mso-fareast-font-family:Calibri">Atenção</span></b>'
            '<span style="background:yellow;mso-highlight:yellow"> prazo</span><o:p></o:p></p>'
            '<!--EndFragment--></body></html>')
    assert html_email.sanitizar(word) == \
        '<p><b><span style="color: #C00000">Atenção</span></b><span style="background-color: yellow"> prazo</span></p>'


def test_font_color_do_navegador_vira_span_e_strike_vira_s():
    assert html_email.sanitizar('<font color="#0070c0">azul</font> <strike>x</strike>') == \
        '<span style="color: #0070c0">azul</span> <s>x</s>'


def test_tags_sem_fechar_sao_fechadas_e_fechamento_solto_e_ignorado():
    assert html_email.sanitizar("<b>a<i>b") == "<b>a<i>b</i></b>"
    assert html_email.sanitizar("a</b></ul>b") == "ab"


def test_links_so_quando_pedido_e_so_https():
    texto = "<div>Arquivo: https://arquivos.exemplo.com.br/x?a=1&b=2</div>"
    assert "<a " not in html_email.sanitizar(texto)
    assert html_email.sanitizar(texto, links=True) == (
        'Arquivo: <a href="https://arquivos.exemplo.com.br/x?a=1&amp;b=2">'
        'https://arquivos.exemplo.com.br/x?a=1&amp;b=2</a>')
    assert "<a " not in html_email.sanitizar("<b>javascript:alert(1)</b>", links=True)


# --- usado pelos testes de cada rota de envio (espelhos, notas, pleitos, protocolos) --------------------------

PERIGOSO = ('<div onclick="roubar()">Bom dia,</div><div><b>Segue</b> a <span style="color: rgb(255, 0, 0); '
            'position: fixed">nota</span>.<script>alert(1)</script><img src=x onerror="alert(2)"></div>')
LIMPO = 'Bom dia,<br><b>Segue</b> a <span style="color: rgb(255, 0, 0)">nota</span>.'


def corpo_enviado(sim) -> str:
    """O corpo do ultimo e-mail gravado pelo simulador do correio (`DASH_GRAPH_SIMULADOR`)."""
    import json
    return json.loads(sorted((sim / "enviados").glob("*.json"))[-1].read_text(encoding="utf-8"))["corpo"]
