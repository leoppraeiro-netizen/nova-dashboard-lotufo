"""Leitura de entidades e certidoes: lista de entidades, tipos e o PDF da certidao.

Bloco 9: o painel antigo, a escrita de entidade e tipo e as decisoes de estado sairam (o cadastro e'
versionado em `cadastro/`; a tela e' Documentos). O checklist do protocolo mora em api_documentos.

O upload e a leitura do PDF sairam daqui no bloco 4 (app/api_documentos.py); as guardas de
arquivo abaixo continuam valendo la', via app/arquivos.py:

* **content-type E magic bytes.** O content-type do multipart e' escolhido pelo cliente
  -- e' declaracao, nao prova. Um `.txt` renomeado para `.pdf` passa por ele. Os 5
  primeiros bytes do conteudo (`%PDF-`) e' que decidem.
* **Teto de 10 MB lido em blocos de 64 KB.** `arquivo.file.read()` inteiro traria o
  upload todo para a memoria antes de qualquer verificacao; em blocos, o excedente e'
  recusado assim que o contador passa do teto. ATENCAO: este teto protege a MEMORIA e
  o arquivo final, nao a banda -- quando o handler roda, o starlette ja recebeu o corpo
  inteiro e o despejou num SpooledTemporaryFile. Limitar o corpo da requisicao em si e'
  trabalho do servidor/proxy da frente (uvicorn/nginx), nao desta rota.
* **O nome em disco e' o sha256 do conteudo, nunca `arquivo.filename`.** O nome do
  cliente e' texto arbitrario: `../../dados/dashboard.db` e `CON.pdf` sao nomes de
  arquivo validos num formulario. Endereco por conteudo mata a classe inteira de
  travessia de caminho e ainda deduplica de graca -- a mesma CND anexada duas vezes
  vira duas linhas (o historico e' append-only) e um arquivo so.

Os PDFs vivem ao lado do banco (`<pasta do banco>/certidoes/`), como os backups: e' o
que faz `DASH_DB_PATH` apontando para um tmp_path nos testes levar os arquivos junto,
sem nunca sujar o `dados/` do repositorio.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app import certidoes, entidades
# As guardas de arquivo moraram aqui ate' o bloco 2; agora vivem em app/arquivos.py, comuns ao
# espelho. Os nomes antigos ficam como aliases (os testes os importam daqui).
from app.arquivos import (BLOCO, MAGIC, MIME, TETO_BYTES, TETO_MB, pasta_certidoes,  # noqa: F401
                          blocos_validados as _blocos_validados,
                          conferir_parseavel as _conferir_parseavel,
                          sha_do_arquivo as _sha_do_arquivo)
from app.api_auth import conexao
from app.api_medicoes import ID
from app.permissoes import exigir

router = APIRouter()

# Maior inteiro que o SQLite grava numa coluna INTEGER (int64). Acima disso o driver
# levanta OverflowError DENTRO do handler -> 500. Mesmo teto de api_medicoes.py.
MAX_INT64 = 9223372036854775807


# --- infraestrutura -------------------------------------------------------------------

def _certidao(conn: sqlite3.Connection, certidao_id: int) -> sqlite3.Row:
    # A faixa do int64 e' checada aqui e nao no pydantic porque `certidao_id` vem da
    # URL: um id acima de int64 vira OverflowError no bind do SQLite (500) antes de
    # qualquer validacao de rota.
    if not 1 <= certidao_id <= MAX_INT64:
        raise HTTPException(404, "Certidão não encontrada")
    r = conn.execute("SELECT * FROM certidoes WHERE id=?", (certidao_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "Certidão não encontrada")
    return r


# --- entidades ------------------------------------------------------------------------

@router.get("/api/entidades")
def listar_entidades(usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
                     conn: sqlite3.Connection = Depends(conexao)):
    return entidades.listar(conn)


# --- tipos de certidao ----------------------------------------------------------------

@router.get("/api/certidoes/tipos")
def listar_tipos(usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
                 conn: sqlite3.Connection = Depends(conexao)):
    return certidoes.tipos(conn)


# --- certidoes ------------------------------------------------------------------------

@router.get("/api/certidoes/{certidao_id}/arquivo")
def baixar(certidao_id: ID,
           usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
           conn: sqlite3.Connection = Depends(conexao)):
    r = _certidao(conn, certidao_id)
    pasta = pasta_certidoes()
    # `arquivo` e' relativo a PASTA DO BANCO ("certidoes/<sha>.pdf"), nao a pasta de
    # certidoes -- e' assim que o upload grava.
    caminho = (pasta.parent / (r["arquivo"] or "")).resolve()
    # A linha de 'nao_se_aplica' guarda '—' no lugar do arquivo (nao existe PDF) e uma
    # linha antiga pode apontar para um arquivo que sumiu do disco. Nos dois casos a
    # resposta certa e' 404 pt-BR, nao um traceback. O teste de containment e' defesa
    # contra caminho torto vindo do banco: o unico lugar de onde um PDF pode sair e'
    # a pasta de certidoes.
    if not caminho.is_relative_to(pasta.resolve()) or not caminho.is_file():
        raise HTTPException(404, "Arquivo da certidão não encontrado")
    # nosniff: sem ele o navegador pode ignorar o content-type e adivinhar pelo
    # conteudo. Um arquivo com HTML dentro seria renderizado como PAGINA, na origem
    # da aplicacao, com a sessao do usuario -- o upload agora exige PDF parseavel,
    # mas o header e' a segunda barreira, para o caso de a primeira falhar um dia.
    return FileResponse(caminho, media_type=MIME, filename=f"certidao-{certidao_id}.pdf",
                        headers={"X-Content-Type-Options": "nosniff"})


