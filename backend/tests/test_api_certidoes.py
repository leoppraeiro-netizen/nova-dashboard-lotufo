"""API de entidades/certidoes: painel, upload endurecido de PDF e download.

O upload e' a unica rota do sistema que recebe BYTES do cliente e os grava em disco --
por isso a maior parte destes testes e' sobre o que ela RECUSA (tipo errado, arquivo
gigante, quem nao pode escrever) e nao sobre o caminho feliz.
"""
import datetime
import hashlib

import pytest

from app import auth, db, leitura_pdf, tempo
# O montador de PDF de mentira (1 pagina, xref com offsets reais) mora no conftest.
# Aqui ele passou a ser NECESSARIO no gate 2: o upload agora abre o arquivo com o
# pypdf antes de arquivar, e "%PDF-" seguido de qualquer coisa nao passa mais.
from tests.conftest import _pdf_com_texto

PDF = _pdf_com_texto("CERTIDAO NEGATIVA DE DEBITOS - VALIDADE: 01/11/2026")
SHA_PDF = hashlib.sha256(PDF).hexdigest()
HOJE = datetime.date(2026, 9, 1)


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    """Semaforo e vigencia dependem de "hoje": sem congelar, o teste passa hoje e
    quebra sozinho quando as datas fixas abaixo vencerem."""
    monkeypatch.setattr(tempo, "hoje_local", lambda: HOJE)


@pytest.fixture(autouse=True)
def prazo_de_leitura_folgado(monkeypatch):
    """Issue #19: com a CPU freada, a leitura em subprocesso (10 s) estourava e o upload
    voltava 422 sem arquivar nada. Estes testes nao sao sobre o prazo (isso e' do
    test_leitura_pdf): folga para todos os que sobem PDF."""
    monkeypatch.setattr(leitura_pdf, "TEMPO_LIMITE_S", 60.0)


def _login(client, perfil, email):
    conn = db.get_conn()
    auth.criar_usuario(conn, "U", email, "senha-forte-123", perfil)
    conn.close()
    r = client.post("/api/auth/login", json={"email": email, "senha": "senha-forte-123"})
    assert r.status_code == 200, r.text
    client.cookies.set("sessao", r.cookies.get("sessao") or client.cookies.get("sessao"))
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    return client


# Bloco 4: `/api/certidoes/upload` saiu; o upload agora e' `/api/documentos/certidoes`, que le o PDF
# e, sem texto legivel (o PDF de laboratorio tem menos de 80 caracteres), aceita os campos
# digitados. As guardas de arquivo (content-type, %PDF-, 10 MB, PDF que nao abre, bomba) sao as
# mesmas de antes (app/arquivos.py + leitura_pdf em subprocesso) -- por isso este helper continua
# servindo aos testes delas. `tipo_id` dos testes antigos vira a chave do tipo.
_CHAVE_DO_TIPO = {1: "federal", 2: "fgts", 3: "trabalhista"}


def _upload(client, conteudo=PDF, mime="application/pdf", nome="cnd.pdf", **campos):
    dados = {"entidade_id": 1, "tipo_id": 1, "natureza": "negativa",
             "emissao": "2026-08-01", "validade": "2026-11-01"}
    dados.update(campos)
    dados["tipo"] = _CHAVE_DO_TIPO.get(int(dados.pop("tipo_id")), "tipo-inexistente")
    return client.post("/api/documentos/certidoes",
                       files={"arquivo": (nome, conteudo, mime)},
                       data={k: str(v) for k, v in dados.items()})


def _linha(client, entidade_id=1, tipo_id=1):
    # o painel antigo (GET /api/certidoes) saiu no bloco 9; a linha vem do repositorio
    from app import certidoes
    conn = db.get_conn()
    try:
        painel = certidoes.painel(conn)
    finally:
        conn.close()
    return [l for l in painel
            if l["entidade_id"] == entidade_id and l["tipo_id"] == tipo_id][0]


def _entidade_desativada():
    # a escrita de entidade pela API saiu no bloco 9 (cadastro versionado)
    from app import entidades
    conn = db.get_conn()
    try:
        eid = entidades.criar(conn, None, {"nome": "Consórcio Lotufo-Alfa", "cnpj": "11.444.777/0001-61",
                                           "papel": "consorcio"})
        entidades.desativar(conn, None, eid)
        return eid
    finally:
        conn.close()


# --- fluxo feliz ----------------------------------------------------------------------

def test_upload_painel_e_download(client_admin, tmp_path):
    r = _upload(client_admin)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    linha = _linha(client_admin)
    assert linha["semaforo"] == "verde"          # vence em 2026-11-01, hoje 2026-09-01
    assert linha["vigente"]["id"] == cid
    assert linha["vigente"]["sha256"] == SHA_PDF
    assert linha["vigente"]["origem"] == "upload"

    d = client_admin.get(f"/api/certidoes/{cid}/arquivo")
    assert d.status_code == 200
    assert d.headers["content-type"] == "application/pdf"
    # o que volta e' byte a byte o que subiu
    assert hashlib.sha256(d.content).hexdigest() == SHA_PDF

    # nome em disco = sha256, NUNCA "cnd.pdf"
    nomes = {p.name for p in (tmp_path / "certidoes").iterdir()}
    assert nomes == {f"{SHA_PDF}.pdf"}


def test_numero_opcional_e_gravado(client_admin):
    cid = _upload(client_admin, numero="CND-2026-000123").json()["id"]
    assert _linha(client_admin)["vigente"]["numero"] == "CND-2026-000123"
    assert client_admin.get(f"/api/certidoes/{cid}/arquivo").status_code == 200


# --- endurecimento do upload ----------------------------------------------------------

def test_txt_renomeado_para_pdf_da_415(client_admin, tmp_path):
    """Content-type mente com facilidade (o cliente escolhe): quem decide sao os
    magic bytes do proprio conteudo."""
    r = _upload(client_admin, conteudo=b"nao sou um PDF, sou um txt renomeado")
    assert r.status_code == 415, r.text
    assert "PDF" in r.json()["detail"]
    # e nada foi gravado em disco
    assert list((tmp_path / "certidoes").glob("*")) == []


def test_content_type_errado_da_415(client_admin):
    """Magic bytes certos nao bastam: o content-type declarado tambem tem que bater."""
    r = _upload(client_admin, mime="text/plain")
    assert r.status_code == 415, r.text


def test_arquivo_vazio_ou_curto_demais_da_415(client_admin):
    assert _upload(client_admin, conteudo=b"").status_code == 415
    assert _upload(client_admin, conteudo=b"%PD").status_code == 415


def test_arquivo_acima_de_10mb_da_413(client_admin, tmp_path):
    grande = b"%PDF-1.7\n" + b"0" * (11 * 1024 * 1024)
    r = _upload(client_admin, conteudo=grande)
    assert r.status_code == 413, r.text
    assert "10" in r.json()["detail"]
    # o temporario nao pode ficar para tras
    assert list((tmp_path / "certidoes").glob("*")) == []


def test_mesmo_pdf_duas_vezes_dedupe_o_arquivo(client_admin, tmp_path):
    """Bloco 4: a MESMA certidao (empresa, tipo, emissao e validade) anexada de novo e' recusada
    como repetida (409); outra emissao com o mesmo PDF vira linha nova, e o arquivo em disco
    continua UM so' (o nome e' o hash do conteudo)."""
    a = _upload(client_admin).json()["id"]
    assert _upload(client_admin).status_code == 409
    b = _upload(client_admin, emissao="2026-08-02").json()["id"]
    assert a != b
    assert [p.name for p in (tmp_path / "certidoes").iterdir()] == [f"{SHA_PDF}.pdf"]
    for cid in (a, b):
        assert client_admin.get(f"/api/certidoes/{cid}/arquivo").content == PDF


def test_validade_antes_da_emissao_da_422_e_nao_trava_a_proxima(client_admin):
    r = _upload(client_admin, emissao="2026-08-01", validade="2026-07-01")
    assert r.status_code == 422, r.text
    assert "validade" in r.json()["detail"].lower()
    # rollback feito: a escrita seguinte funciona normalmente
    assert _upload(client_admin).status_code == 201


def test_data_invalida_e_numero_longo_dao_422(client_admin):
    assert _upload(client_admin, emissao="01/08/2026").status_code == 422
    assert _upload(client_admin, numero="N" * 101).status_code == 422
    assert _upload(client_admin, numero="N" * 100).status_code == 201


# --- 404 antes do repositorio ---------------------------------------------------------

def test_404s(client_admin):
    assert _upload(client_admin, entidade_id=99999).status_code == 404
    # bloco 4: o tipo e' uma das seis chaves (validado pelo esquema da rota) -> 422, nao 404
    assert _upload(client_admin, tipo_id=99999).status_code == 422
    assert client_admin.get("/api/certidoes/99999/arquivo").status_code == 404
    assert client_admin.post("/api/certidoes/99999/estado",
                             json={"estado": "revogada"}).status_code == 404
    assert client_admin.post("/api/entidades/99999/desativar").status_code == 404


def test_id_absurdo_nao_vira_500(client_admin):
    """int acima de int64 estoura OverflowError no driver do SQLite (500)."""
    # A-07 (10/10/2026): o teto de id de caminho e' validado na entrada -> 422, nao mais 404 do handler
    assert client_admin.get("/api/certidoes/99999999999999999999/arquivo").status_code == 422
    assert _upload(client_admin, entidade_id=99999999999999999999).status_code == 422


def test_certidao_sem_arquivo_nao_baixa(client_admin):
    """'nao_se_aplica' e' linha de certidao SEM PDF real (arquivo = '—'): o download
    tem que dar 404 pt-BR, nao 500 procurando um arquivo que nunca existiu."""
    from app import certidoes
    conn = db.get_conn()
    cid = certidoes.marcar_nao_se_aplica(conn, 1, 1, 1, "não é contribuinte municipal")
    conn.close()
    r = client_admin.get(f"/api/certidoes/{cid}/arquivo")
    assert r.status_code == 404, r.text
    assert "arquivo" in r.json()["detail"].lower()


# --- entidades e tipos ----------------------------------------------------------------

def test_entidade_desativada_nao_recebe_certidao(client_admin):
    eid = _entidade_desativada()
    r = _upload(client_admin, entidade_id=eid)
    assert r.status_code == 422, r.text
    assert "desativada" in r.json()["detail"].lower()


# --- estado ---------------------------------------------------------------------------

# --- 'nao se aplica' num par SEM certidao (ruling R11) --------------------------------
#
# A rota de estado (`/{certidao_id}/estado`) so' alcanca um par que JA TEM certidao --
# ela precisa de um id para marcar. O caso que mais aparece na mesa e' o oposto: a
# consorciada que nunca teve inscricao estadual e por isso NUNCA vai ter aquela
# certidao. Sem esta rota o par ficava vermelho para sempre e o checklist de protocolo
# acusava uma pendencia que ninguem tinha como resolver.

# --- permissoes -----------------------------------------------------------------------

def test_leitura_exige_login(client):
    for rota in ("/api/certidoes/tipos", "/api/entidades", "/api/certidoes/1/arquivo"):
        assert client.get(rota).status_code in (401, 403), rota


def test_diretoria_le_mas_nao_faz_upload(client):
    c = _login(client, "diretoria", "dir@lotufo.com")
    assert c.get("/api/entidades").status_code == 200
    assert _upload(c).status_code == 403


def test_engenharia_faz_upload(client):
    c = _login(client, "engenharia", "eng@lotufo.com")
    assert _upload(c).status_code == 201


def test_mutacoes_exigem_csrf(client_admin):
    del client_admin.headers["X-CSRF-Token"]
    assert _upload(client_admin).status_code == 403


# --- gate 2: correcoes do revisor externo ---------------------------------------------

def _arquivos(tmp_path):
    return sorted(p.name for p in (tmp_path / "certidoes").glob("*"))


def test_422_de_dominio_nao_deixa_arquivo_em_disco(client_admin, tmp_path):
    """Item 5 do gate 2. O PDF era gravado ANTES da validacao de dominio: cada 422
    repetido (um operador insistindo com as datas trocadas) deixava mais um arquivo
    de ate 10 MB na pasta, sem nenhuma certidao apontando para ele. Nada limpa isso.
    """
    for _ in range(3):
        r = _upload(client_admin, emissao="2026-08-01", validade="2026-07-01")
        assert r.status_code == 422, r.text
    assert _arquivos(tmp_path) == []


def test_404_de_entidade_ou_tipo_nao_deixa_arquivo_em_disco(client_admin, tmp_path):
    assert _upload(client_admin, entidade_id=99999).status_code == 404
    assert _upload(client_admin, tipo_id=99999).status_code == 422
    assert _arquivos(tmp_path) == []


def test_entidade_desativada_nao_deixa_arquivo_em_disco(client_admin, tmp_path):
    eid = _entidade_desativada()
    assert _upload(client_admin, entidade_id=eid).status_code == 422
    assert _arquivos(tmp_path) == []


def test_pdf_com_assinatura_mas_ilegivel_da_415(client_admin, tmp_path):
    """Item 6 do gate 2. '%PDF-' sao 5 bytes -- prova de intencao, nao de conteudo.
    Um arquivo truncado ou corrompido passava e virava certidao com semaforo verde
    apontando para algo que nenhum leitor abre. Quem descobre e' o orgao, na sessao.
    """
    r = _upload(client_admin, conteudo=b"%PDF-1.4 lixo")
    assert r.status_code == 415, r.text
    # B-08 (10/10/2026): sem o nome da excecao ("(ValueError)") na frase ao usuario
    assert r.json()["detail"] == "PDF inválido ou corrompido — envie o arquivo original emitido pelo órgão"
    assert _arquivos(tmp_path) == []       # nem o temporario sobrou


def test_download_manda_nao_adivinhar_o_tipo(client_admin):
    """Item 6 do gate 2. Sem `nosniff`, o navegador pode ignorar o content-type e
    adivinhar pelo conteudo -- e um PDF com HTML dentro seria renderizado como
    pagina, na origem da aplicacao."""
    cid = _upload(client_admin).json()["id"]
    d = client_admin.get(f"/api/certidoes/{cid}/arquivo")
    assert d.status_code == 200
    assert d.headers["x-content-type-options"] == "nosniff"


def test_dedupe_confere_o_conteudo_e_substitui_arquivo_divergente(client_admin, tmp_path):
    """Item 7 do gate 2. O dedupe confiava no NOME: `<sha>.pdf` existindo bastava
    para descartar o upload recem-recebido. Se o arquivo antigo estivesse truncado
    (queda de disco, copia parcial de backup), o novo -- integro -- era jogado fora e
    a certidao passava a apontar para lixo, com o sha256 do banco mentindo.
    """
    pasta = tmp_path / "certidoes"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{SHA_PDF}.pdf").write_bytes(b"%PDF-1.4 arquivo corrompido pre-existente")

    cid = _upload(client_admin).json()["id"]
    assert (pasta / f"{SHA_PDF}.pdf").read_bytes() == PDF
    d = client_admin.get(f"/api/certidoes/{cid}/arquivo")
    assert hashlib.sha256(d.content).hexdigest() == SHA_PDF


def test_dedupe_preserva_arquivo_integro_ja_arquivado(client_admin, tmp_path):
    """A correcao do item 7 nao pode reescrever o que ja esta certo: conteudo igual,
    mesmo arquivo, sem regravar."""
    assert _upload(client_admin).status_code == 201
    alvo = tmp_path / "certidoes" / f"{SHA_PDF}.pdf"
    antes = alvo.stat().st_mtime_ns
    _upload(client_admin)
    assert alvo.stat().st_mtime_ns == antes and alvo.read_bytes() == PDF


# --- item 8: o download nunca sai da pasta de certidoes -------------------------------

def _certidao_apontando_para(arquivo: str) -> int:
    """Grava uma certidao com `arquivo` torto -- o que um banco restaurado de outra
    maquina, ou uma linha antiga, pode conter. A rota nunca pode obedecer."""
    from app import certidoes
    conn = db.get_conn()
    try:
        return certidoes.registrar(conn, 1, 1, 1, "2026-08-01", "2026-11-01",
                                   arquivo, "a" * 64, "upload")
    finally:
        conn.close()


def test_download_recusa_travessia_de_caminho(client_admin):
    cid = _certidao_apontando_para("../../x")
    assert client_admin.get(f"/api/certidoes/{cid}/arquivo").status_code == 404


def test_download_recusa_caminho_absoluto_fora_da_pasta(client_admin, tmp_path):
    fora = tmp_path / "fora.pdf"
    fora.write_bytes(PDF)
    cid = _certidao_apontando_para(str(fora))
    r = client_admin.get(f"/api/certidoes/{cid}/arquivo")
    assert r.status_code == 404, r.text
    assert fora.exists()          # e o arquivo de fora nunca foi lido nem tocado


def test_download_de_arquivo_referenciado_mas_ausente(client_admin, tmp_path):
    cid = _upload(client_admin).json()["id"]
    (tmp_path / "certidoes" / f"{SHA_PDF}.pdf").unlink()
    r = client_admin.get(f"/api/certidoes/{cid}/arquivo")
    assert r.status_code == 404 and "arquivo" in r.json()["detail"].lower()


# --- item 9: toda mutacao exige CSRF --------------------------------------------------

def test_upload_recusa_bomba_de_descompressao_com_415(client_admin, tmp_path):
    """A mesma guarda vale para a porta que ARQUIVA: as duas abrem o PDF pelo mesmo
    leitor, e a frase pt-BR chega inteira em vez de virar "PDF inválido ou corrompido"."""
    from app import leitura_pdf
    bomba = _pdf_com_texto("0" * (leitura_pdf.TETO_STREAM_BYTES + 1_000_000), comprimir=True)
    r = _upload(client_admin, conteudo=bomba)
    assert r.status_code == 415, r.text
    assert "comprimido" in r.json()["detail"]
    assert _arquivos(tmp_path) == []       # nem o temporario sobrou


def test_rotas_de_ia_nao_existem_mais(client_admin):
    assert client_admin.post("/api/certidoes/extrair",
                             files={"arquivo": ("x.pdf", PDF, "application/pdf")}).status_code == 404
    assert client_admin.get("/api/ia/chamadas").status_code == 404
