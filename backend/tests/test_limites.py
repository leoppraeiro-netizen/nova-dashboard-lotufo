"""A-04 (testes de quebra 10/10/2026): corpo gigante era lido inteiro antes do 401.

O teto vale para todo pedido, antes de qualquer rota: 45 MB para multipart (a maior rota de upload aceita 40 MB)
e 2 MB para o resto. Com Content-Length acima do teto, 413 sem ler o corpo; sem Content-Length (chunked), a
leitura para no byte que passa do teto."""
MB = 1024 * 1024
FRONTEIRA = "limite-teste"


def _multipart(tamanho: int) -> bytes:
    cabeca = (f"--{FRONTEIRA}\r\nContent-Disposition: form-data; name=\"tipo\"\r\n\r\noutro\r\n"
              f"--{FRONTEIRA}\r\nContent-Disposition: form-data; name=\"arquivo\"; filename=\"a.pdf\"\r\n"
              "Content-Type: application/pdf\r\n\r\n%PDF-").encode()
    pe = f"\r\n--{FRONTEIRA}--\r\n".encode()
    return cabeca + b"0" * (tamanho - len(cabeca) - len(pe)) + pe


def _post_multipart(client, tamanho):
    return client.post("/api/protocolos/1/pecas", content=_multipart(tamanho),
                       headers={"Content-Type": f"multipart/form-data; boundary={FRONTEIRA}"})


def test_json_de_3_mb_sem_login_da_413(client):
    corpo = b'{"campo":"atestado","valor":"1,00","x":"' + b"A" * (3 * MB) + b'"}'
    r = client.put("/api/medicoes/1/valor", content=corpo, headers={"Content-Type": "application/json"})
    assert r.status_code == 413, r.text
    assert r.json() == {"detail": "Pedido acima do tamanho permitido"}


def test_json_pequeno_sem_login_continua_401(client):
    r = client.put("/api/medicoes/1/valor", json={"campo": "atestado", "valor": "1,00"})
    assert r.status_code == 401


def test_json_chunked_acima_do_teto_da_413(client):
    def pedacos():
        yield b'{"x":"'
        for _ in range(3):
            yield b"A" * MB
        yield b'"}'
    r = client.put("/api/medicoes/1/valor", content=pedacos(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413, r.text
    assert r.json() == {"detail": "Pedido acima do tamanho permitido"}


def test_multipart_de_46_mb_da_413(client):
    r = _post_multipart(client, 46 * MB)
    assert r.status_code == 413, r.text
    assert r.json() == {"detail": "Pedido acima do tamanho permitido"}


def test_multipart_legitimo_passa_pelo_teto(client):
    # 10 MB (peca comum) e 41 MB (acima dos 40 MB da rota, abaixo dos 45 MB do teto geral): chegam a' rota como
    # antes, e quem responde e' ela (401 sem login; o teto de 40 MB da peca continua sendo dela).
    for tamanho in (10 * MB, 41 * MB):
        assert _post_multipart(client, tamanho).status_code == 401


# --- Gate Sol S2 (10/10/2026): o teto de 45 MB e' das ROTAS de upload, nao de quem declara multipart ---

def test_json_declarado_multipart_para_rota_json_da_413(client):
    corpo = b'{"x":"' + b"A" * (3 * MB) + b'"}'
    r = client.post("/api/protocolos/envio", content=corpo,
                    headers={"Content-Type": f"multipart/form-data; boundary={FRONTEIRA}"})
    assert r.status_code == 413, r.text


def test_multipart_de_10_mb_para_rota_json_da_413(client):
    r = client.put("/api/medicoes/1/valor", content=_multipart(10 * MB),
                   headers={"Content-Type": f"multipart/form-data; boundary={FRONTEIRA}"})
    assert r.status_code == 413, r.text


def test_toda_rota_com_formulario_esta_na_lista_de_upload(client):
    # guarda: rota nova com UploadFile/Form que nao entrar em ROTAS_UPLOAD ficaria presa nos 2 MB sem ninguem notar
    # pelo OpenAPI (rota com formulario declara corpo multipart/urlencoded): a lista de rotas do app nao e' plana
    # nesta versao do FastAPI (routers incluidos ficam aninhados)
    import re
    from app import limites
    com_formulario = [(metodo.upper(), re.sub(r"\{[^}]+\}", "1", caminho))
                      for caminho, ops in client.app.openapi()["paths"].items() for metodo, op in ops.items()
                      if {"multipart/form-data", "application/x-www-form-urlencoded"}
                      & set(op.get("requestBody", {}).get("content", {}))]
    assert len(com_formulario) >= 12
    for metodo, caminho in com_formulario:
        assert limites.rota_de_upload(metodo, caminho), (metodo, caminho)
    assert not limites.rota_de_upload("POST", "/api/protocolos/envio")
    assert not limites.rota_de_upload("PUT", "/api/medicoes/1/valor")
