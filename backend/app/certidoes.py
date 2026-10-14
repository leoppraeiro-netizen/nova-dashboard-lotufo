"""Certidoes negativas: historico append-only, vigencia NA DATA e semaforo (spec §5).

Tres decisoes que sustentam o resto:

1. RENOVAR NAO SOBRESCREVE. Cada emissao e' uma linha nova. E' o que permite responder,
   meses depois, "qual certidao estava valendo no dia do protocolo X" -- a pergunta que o
   orgao faz quando ameaca glosar. Um UPDATE na linha antiga apagaria a prova.
2. 'vencida' NAO E' ESTADO GRAVADO. E' derivado de `validade < hoje` no momento da leitura.
   Gravar exigiria um job diario para manter a coluna honesta; se ele falhar num feriado,
   o painel mostra verde numa certidao vencida -- exatamente o erro que o painel existe
   para evitar. So entra em `estado` o que um humano DECIDE: 'revogada' e 'nao_se_aplica'.
3. 'nao_se_aplica' e' LINHA DE CERTIDAO, nao flag na matriz entidade x tipo. Mantem quem
   decidiu, quando e por que -- auditavel como qualquer outro dado.

Hoje = `tempo.hoje_local()` (America/Cuiaba), nunca `date.today()`: as 21h do dia 31 em
Cuiaba o servidor em UTC ja virou o mes, e uma certidao que vence "hoje" apareceria vencida.
"""
import datetime
import re
import sqlite3

from app import auditoria, db, entidades, tempo

JURISDICOES = ("federal", "estadual", "municipal", "trabalhista")
ORIGENS = ("robo", "upload")
# Bloco 4: natureza lida do documento; positiva pura nunca e' gravada (o leitor recusa).
NATUREZAS = ("negativa", "positiva_efeito_negativa")
# 'vigente' nao entra: e' o estado de nascimento (default do schema), nao algo que se marca.
# 'vencida' nao existe -- e' derivada da validade.
ESTADOS_MARCAVEIS = ("revogada", "nao_se_aplica")
# Como cada estado marcado aparece numa frase pt-BR de erro.
_ROTULO_ESTADO = {"revogada": "revogada",
                  "nao_se_aplica": "marcada como 'não se aplica'"}
DIAS_ALERTA = 15                  # <= 15 dias para vencer => ambar (spec §5)

_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_SEM_ARQUIVO = "—"                # placeholder da linha de 'nao_se_aplica'


def _data(valor, campo: str) -> str:
    try:
        return datetime.date.fromisoformat(valor).isoformat()
    except (TypeError, ValueError):
        raise ValueError(f"{campo} inválida: {valor!r} (use AAAA-MM-DD)") from None


# --- tipos ----------------------------------------------------------------------------

def tipos(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM certidao_tipos ORDER BY jurisdicao, nome, id")]


def criar_tipo(conn: sqlite3.Connection, usuario_id: int, nome: str, jurisdicao: str,
               emissor: str, aplicavel_por_padrao: bool) -> int:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Nome do tipo de certidão é obrigatório")
    if jurisdicao not in JURISDICOES:
        raise ValueError(f"Jurisdição inválida: {jurisdicao} "
                         f"(use {', '.join(repr(j) for j in JURISDICOES)})")
    emissor = (emissor or "").strip()
    if not emissor:
        raise ValueError("Emissor do tipo de certidão é obrigatório")
    padrao = 1 if aplicavel_por_padrao else 0
    duplicado = f"Tipo de certidão '{nome}' ({jurisdicao}) já existe"
    with db.mutacao(conn):
        if conn.execute("SELECT id FROM certidao_tipos WHERE nome=? AND jurisdicao=?",
                        (nome, jurisdicao)).fetchone():
            raise ValueError(duplicado)
        try:
            cur = conn.execute(
                "INSERT INTO certidao_tipos (nome, jurisdicao, emissor, aplicavel_por_padrao) "
                "VALUES (?,?,?,?)", (nome, jurisdicao, emissor, padrao))
        except sqlite3.IntegrityError as e:
            if "UNIQUE" not in str(e).upper():
                raise
            raise ValueError(duplicado) from e
        tid = cur.lastrowid
        auditoria.registrar(conn, usuario_id, "certidao_tipo.criar", "certidao_tipo", tid, None,
                            {"nome": nome, "jurisdicao": jurisdicao, "emissor": emissor,
                             "aplicavel_por_padrao": padrao})
    return tid


# --- certidoes ------------------------------------------------------------------------

def _inserir(conn, usuario_id, entidade_id, tipo_id, numero, emissao, validade, arquivo,
             sha256, origem, estado, observacao, acao, estado_em=None, natureza=None, leitura=None,
             nome_original=None) -> int:
    with db.mutacao(conn):
        # Checar FK na aplicacao para dar erro de DOMINIO (422 pt-BR) em vez de deixar o
        # IntegrityError cru virar 500 no handler.
        if entidades.detalhe(conn, entidade_id) is None:
            raise ValueError(f"Entidade {entidade_id} não encontrada")
        if conn.execute("SELECT 1 FROM certidao_tipos WHERE id=?", (tipo_id,)).fetchone() is None:
            raise ValueError(f"Tipo de certidão {tipo_id} não encontrado")
        cur = conn.execute(
            "INSERT INTO certidoes (entidade_id, tipo_id, numero, emissao, validade, arquivo, "
            "sha256, origem, estado, observacao, estado_em, natureza, leitura, nome_original) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (entidade_id, tipo_id, numero, emissao, validade, arquivo, sha256.lower(),
             origem, estado, observacao, estado_em, natureza, leitura, nome_original))
        cid = cur.lastrowid
        auditoria.registrar(conn, usuario_id, acao, "certidao", cid, None,
                            {"entidade_id": entidade_id, "tipo_id": tipo_id, "numero": numero,
                             "emissao": emissao, "validade": validade, "arquivo": arquivo,
                             "sha256": sha256.lower(), "origem": origem, "estado": estado,
                             "observacao": observacao, "estado_em": estado_em,
                             "natureza": natureza, "leitura": leitura, "nome_original": nome_original})
    return cid


def registrar(conn: sqlite3.Connection, usuario_id: int | None, entidade_id: int,
              tipo_id: int, emissao: str, validade: str, arquivo: str, sha256: str,
              origem: str, numero: str | None = None, natureza: str | None = None,
              leitura: str | None = None, nome_original: str | None = None,
              observacao: str | None = None) -> int:
    """Grava UMA emissao. Renovacao chama isto de novo -- a anterior fica onde esta.

    `usuario_id=None` fica aceito para importacoes sem humano (nenhuma existe hoje; o
    robo da fase 3 foi descartado pela spec §15.2). A coluna do audit_log e' nullable,
    e quem fez continua distinguivel pelo `origem` da propria certidao.
    """
    emissao = _data(emissao, "Data de emissão")
    validade = _data(validade, "Data de validade")
    if validade <= emissao:
        raise ValueError(f"A validade ({validade}) precisa ser posterior à emissão ({emissao})")
    if natureza not in NATUREZAS + (None,):
        raise ValueError(f"Natureza inválida: {natureza!r} (use 'negativa' ou 'positiva_efeito_negativa')")
    if leitura not in ("automatica", "manual", None):
        raise ValueError(f"Leitura inválida: {leitura!r}")
    if origem not in ORIGENS:
        raise ValueError(f"Origem inválida: {origem} (use 'robo' ou 'upload')")
    if not (arquivo or "").strip():
        raise ValueError("Arquivo da certidão é obrigatório")
    # O sha256 e' a prova de que o PDF arquivado e' o mesmo que o orgao emitiu; aceitar
    # qualquer string aqui esvaziaria a garantia sem ninguem perceber.
    if not _SHA256.fullmatch(sha256 or ""):
        raise ValueError("sha256 inválido: informe os 64 caracteres hexadecimais do arquivo")
    return _inserir(conn, usuario_id, entidade_id, tipo_id, numero, emissao, validade,
                    arquivo.strip(), sha256, origem, "vigente", observacao, "certidao.registrar",
                    natureza=natureza, leitura=leitura, nome_original=nome_original)


def marcar_nao_se_aplica(conn: sqlite3.Connection, usuario_id: int, entidade_id: int,
                         tipo_id: int, observacao: str | None = None) -> int:
    """Declara que a entidade nao esta sujeita aquele tipo de certidao.

    Vira linha de certidao SEM arquivo real (sha256 de 64 zeros, emissao=validade=hoje)
    justamente para manter auditavel QUEM decidiu -- uma flag na matriz nao guardaria isso.

    RECUSA quando o par TEM certidao valendo hoje: "não se aplica" e "aqui está a
    certidão" sao afirmacoes contrarias sobre o mesmo par, e a declaracao entra como
    linha NOVA -- ou seja, como a decisao mais recente (`nao_se_aplica_vigora`). O
    painel virava cinza e o checklist parava de cobrar um tipo para o qual existe
    documento valido arquivado, escondendo a certidao que a mesa acabou de anexar. A
    saida legitima e' esperar a certidao vencer ou revoga-la primeiro, que e' decisao
    com dono e data.
    """
    hoje = tempo.hoje_local().isoformat()
    # A conferencia mora DENTRO da transacao (o `db.mutacao` e' reentrante, e o
    # `_inserir` compoe com este): fora dela, uma certidao gravada entre a leitura e o
    # INSERT deixaria passar exatamente a contradicao que a guarda existe para barrar.
    with db.mutacao(conn):
        v = vigente(conn, entidade_id, tipo_id)
        if v is not None:
            ate = datetime.date.fromisoformat(v["validade"]).strftime("%d/%m/%Y")
            e = entidades.detalhe(conn, entidade_id)
            nome = e["nome"] if e else entidade_id
            raise ValueError(f"{nome} já tem certidão vigente deste tipo (válida até "
                             f"{ate}); não há o que declarar")
        # `estado_em=hoje`: a linha ja NASCE com estado marcado, entao a data da decisao
        # e' hoje -- mesma semantica de `marcar_estado`, para que as duas portas de
        # 'nao_se_aplica' produzam linhas indistinguiveis para quem le depois.
        return _inserir(conn, usuario_id, entidade_id, tipo_id, None, hoje, hoje,
                        _SEM_ARQUIVO, "0" * 64, "upload", "nao_se_aplica", observacao,
                        "certidao.nao_se_aplica", estado_em=hoje)


def marcar_estado(conn: sqlite3.Connection, usuario_id: int, certidao_id: int, estado: str,
                  observacao: str | None) -> None:
    if estado not in ESTADOS_MARCAVEIS:
        raise ValueError(
            f"Estado inválido: {estado} — só 'revogada' ou 'nao_se_aplica'; "
            "'vencida' é derivada da validade e nunca é gravada")
    hoje = tempo.hoje_local().isoformat()
    with db.mutacao(conn):
        r = conn.execute("SELECT * FROM certidoes WHERE id=?", (certidao_id,)).fetchone()
        if r is None:
            raise ValueError(f"Certidão {certidao_id} não encontrada")
        antes = {"estado": r["estado"], "observacao": r["observacao"],
                 "estado_em": r["estado_em"]}
        # COALESCE: observacao=None PRESERVA a anterior (marcar de novo sem motivo novo nao
        # e' um pedido de esquecer o antigo).
        #
        # `AND estado='vigente'` faz DUAS coisas. Fecha a janela entre a leitura e o
        # UPDATE (como em medicoes.mudar_estado) E, principalmente, impede transicao a
        # partir de estado ja marcado: com `AND estado=?` (o lido), revogar duas vezes
        # passava e gravava DUAS linhas de auditoria para uma decisao que aconteceu uma
        # vez -- e 'nao_se_aplica' em cima de 'revogada' reescrevia `estado_em`,
        # mudando retroativamente a data a partir da qual a certidao deixou de valer.
        # Marcacao de estado e' porta de uma via so: a saida e' emitir certidao nova.
        cur = conn.execute(
            "UPDATE certidoes SET estado=?, observacao=COALESCE(?, observacao), "
            "estado_em=? WHERE id=? AND estado='vigente'",
            (estado, observacao, hoje, certidao_id))
        if cur.rowcount != 1:
            atual = conn.execute("SELECT estado FROM certidoes WHERE id=?",
                                 (certidao_id,)).fetchone()["estado"]
            if atual == "vigente":     # mudou e voltou entre a leitura e o UPDATE
                raise ValueError("Estado da certidão mudou concorrentemente; tente novamente")
            raise ValueError(
                f"A certidão {certidao_id} já está {_ROTULO_ESTADO.get(atual, atual)} — só uma "
                f"certidão vigente muda de estado; para voltar a ter cobertura, "
                f"registre uma emissão nova")
        # Auditar o que FICOU GRAVADO, nao o parametro recebido: com observacao=None,
        # depois={"observacao": None} descreveria um apagamento que o COALESCE nao fez.
        obs_final = observacao if observacao is not None else r["observacao"]
        auditoria.registrar(conn, usuario_id, "certidao.marcar_estado", "certidao", certidao_id,
                            antes, {"estado": estado, "observacao": obs_final,
                                    "estado_em": hoje})


def vigente(conn: sqlite3.Connection, entidade_id: int, tipo_id: int,
            na_data: str | None = None) -> dict | None:
    """A certidao que valia na data pedida (hoje, por padrao) -- ou None.

    `validade >= na_data`: o orgao aceita a certidao ATE o ultimo dia de validade.
    `ORDER BY validade DESC, emissao DESC, id DESC`: se duas emissoes cobrem a mesma data,
    vale a de MAIOR VALIDADE (spec 2026-09-21 §9) -- uma emissao antiga anexada depois da nova
    nao a desbanca; empate na validade fica com a emissao mais recente, e o id evita resultado
    instavel.

    MARCACAO DE ESTADO NAO E' RETROATIVA (gate 2, item 1). Uma certidao revogada em
    setembro VALIA em julho -- e foi protocolada em julho. Filtrar por
    `estado='vigente'` e ponto apagava essa prova: a resposta a "o que valia no dia do
    protocolo X" virava "nada" por causa de uma decisao tomada meses depois. Por isso a
    linha MARCADA continua respondendo pelas datas ANTERIORES a `estado_em`. Linha
    antiga sem `estado_em` (marcada antes da migracao 008) tem NULL, e `NULL > data` e'
    NULL no SQLite: ela some de toda data, como antes -- nao ha data honesta para
    atribuir.

    Vale para OS DOIS estados marcaveis, nao so' para 'revogada' (revisao final, I1). A
    outra porta de 'nao_se_aplica' e' `marcar_estado` numa certidao que EXISTE, com PDF
    e datas reais: so' 'revogada' no filtro fazia essa marcacao apagar o passado da
    certidao -- o mesmo buraco do item 1, pela outra tela.

    A LINHA-PLACEHOLDER de `marcar_nao_se_aplica` continua fora de toda data, sem
    precisar de filtro proprio: ela nasce com `emissao = validade = estado_em = hoje`,
    entao `estado_em > na_data` pede `na_data < hoje` e `emissao <= na_data` pede
    `na_data >= hoje` -- nao existe data que satisfaca as duas. Declaracao de que
    documento nao e' exigido nao e' documento;
    quem a interpreta e' o semaforo (cinza), nao a vigencia.
    """
    # `na_data` chega de fora (querystring, chamador) e ia direto para uma comparacao
    # de STRING no SQL: "2026-9-1" e "lixo" comparavam lexicograficamente e devolviam
    # resposta com cara de certa. Mesmo `_data()` de `registrar`.
    na_data = _data(na_data, "Data de referência") if na_data is not None \
        else tempo.hoje_local().isoformat()
    r = conn.execute(
        "SELECT * FROM certidoes WHERE entidade_id=? AND tipo_id=? "
        "AND (estado='vigente' OR (estado IN ('revogada','nao_se_aplica') "
        "AND estado_em > ?)) "
        "AND emissao <= ? AND validade >= ? ORDER BY validade DESC, emissao DESC, id DESC LIMIT 1",
        (entidade_id, tipo_id, na_data, na_data, na_data)).fetchone()
    return dict(r) if r else None


def nao_se_aplica_vigora(conn: sqlite3.Connection, entidade_id: int, tipo_id: int) -> bool:
    """A ULTIMA linha do par (entidade, tipo) e' um 'nao_se_aplica'?

    Gate 2, item 3: antes bastava EXISTIR uma linha 'nao_se_aplica' no historico para
    o par ficar cinza PARA SEMPRE. Cenario real: NSA em janeiro, a entidade volta a ter
    a obrigacao, apresenta certidao em marco, ela vence em abril -- e o painel continuava
    cinza, escondendo uma pendencia que o orgao ia cobrar. So a decisao MAIS RECENTE
    manda.

    `ORDER BY id DESC`, e NAO `emissao DESC` (revisao final, I2). A pergunta aqui e'
    "qual foi a ULTIMA DECISAO do par", nao "qual documento cobre a data" -- e a ordem
    das decisoes e' a ordem em que elas foram gravadas, que num historico append-only
    e' o id. Ordenando por emissao, uma certidao anexada DEPOIS de um NSA mas com
    emissao ANTERIOR a ele (certidao antiga que a mesa achou na pasta) perdia para o
    NSA: enquanto ela valia o painel mostrava a certidao (`vigente` manda quando ha
    cobertura), e no dia em que ela vencia o par voltava a CINZA por causa de uma
    declaracao que a mesa ja tinha contrariado ao anexar o documento.
    """
    r = conn.execute(
        "SELECT estado FROM certidoes WHERE entidade_id=? AND tipo_id=? "
        "ORDER BY id DESC LIMIT 1", (entidade_id, tipo_id)).fetchone()
    return r is not None and r["estado"] == "nao_se_aplica"


def ultima_emissao(conn: sqlite3.Connection, entidade_id: int, tipo_id: int,
                   na_data: str | None = None) -> dict | None:
    """A ultima emissao do par que JA VENCEU -- ou None (nunca houve nenhuma).

    Existe para a matriz distinguir duas coisas que o semaforo pinta igual: "venceu em
    13/08" e "nunca foi cadastrada". Para quem opera sao problemas diferentes (renovar
    x emitir pela primeira vez), e a linha vermelha com quatro tracos escondia a
    diferenca -- o historico ja estava no banco.

    `estado='vigente'`: linha revogada ou 'nao_se_aplica' nao e' emissao vencida, e' outra
    decisao. `validade < na_data`: a que ainda vale e' respondida por `vigente()`; sem o
    filtro, uma emissao com data futura (registrada antes de comecar a valer) apareceria
    como "vencida em" uma data que ainda nem chegou.
    `ORDER BY id DESC`: append-only, entao o maior id e' a ultima que alguem arquivou.
    """
    na_data = _data(na_data, "Data de referência") if na_data is not None \
        else tempo.hoje_local().isoformat()
    r = conn.execute(
        "SELECT * FROM certidoes WHERE entidade_id=? AND tipo_id=? AND estado='vigente' "
        "AND validade < ? ORDER BY id DESC LIMIT 1",
        (entidade_id, tipo_id, na_data)).fetchone()
    return dict(r) if r else None


def painel(conn: sqlite3.Connection) -> list[dict]:
    """Matriz entidade (ativa) x tipo com semaforo.

    verde: vence em mais de 15 dias | ambar: vence em <= 15 (inclui hoje)
    vermelho: vencida, revogada ou nunca cadastrada | cinza: nao cobrado

    Cinza tem DOIS motivos, e o campo `motivo` diz qual: 'nao_se_aplica' (alguem
    declarou, com nome e data) e 'nao_cobrada' (o TIPO nao e' cobrado por padrao). O
    segundo e' a correcao do passe visual: `checklist.py` e `paineis.py` so' cobram
    tipos `aplicavel_por_padrao`, e a matriz pintava vermelho o mesmo par -- a tela
    dizia "pendente" enquanto o checklist do contrato dizia "pronto".

    QUEM MANDA E' A REGRA 3 DO CHECKLIST (docstring de `checklist.py`): "tipo cadastrado
    como excecao nao pode reprovar todo mundo por omissao; quando ele passar a ser
    exigido de fato, o cadastro do TIPO e' que muda". Por isso o par com
    `aplicavel_por_padrao = 0` e SEM certidao valendo hoje fica cinza/'nao_cobrada'
    MESMO com uma emissao vencida no historico (decisao R15): vermelho ali seria a
    matriz cobrando sozinha uma exigencia que nem o checklist nem os alertas cobram --
    a divergencia que esta correcao existe para fechar. A emissao vencida continua
    viajando em `ultima`, como INFORMACAO (a tela mostra as datas dela); ela nao entra
    no contador "Sem cobertura".

    COM certidao vigente o tipo nao cobrado se comporta como qualquer outro
    (verde/ambar): o que esta valendo hoje e' fato, nao exigencia.
    """
    hoje = tempo.hoje_local()
    # `na_data=hoje` EXPLICITO: sem ele cada `vigente()` lia o relogio de novo, e uma
    # montagem de painel iniciada as 23h59 podia comparar metade das linhas com um dia
    # e a outra metade com o seguinte -- duas datas na mesma resposta (M11). Uma leitura
    # do relogio por resposta e' o mesmo criterio de `ultima_emissao` logo abaixo.
    hoje_iso = hoje.isoformat()
    todos_tipos = tipos(conn)
    out = []
    for e in entidades.listar(conn):
        for t in todos_tipos:
            v = vigente(conn, e["id"], t["id"], na_data=hoje_iso)
            nsa = nao_se_aplica_vigora(conn, e["id"], t["id"])
            # So' faz sentido perguntar pela ultima vencida quando nao ha vigente: com
            # cobertura hoje, o que a matriz mostra e' a certidao que vale. Ela vem
            # para TODO par sem cobertura -- inclusive o cinza 'nao_cobrada' --, porque
            # e' informacao ("a ultima venceu em 13/08"), nao veredito.
            ultima = None if v else ultima_emissao(conn, e["id"], t["id"], hoje_iso)
            dias = None
            motivo = None
            if v:
                dias = (datetime.date.fromisoformat(v["validade"]) - hoje).days
                sem = "verde" if dias > DIAS_ALERTA else "ambar"
            elif nsa:
                # 'nao_se_aplica' so pinta cinza quando NAO ha certidao valendo E a
                # declaracao e' a decisao mais recente do par: se a entidade voltou a
                # ter a obrigacao e ja apresentou certidao, o que manda e' a certidao
                # -- mesmo depois de ela vencer (ai o par fica vermelho, nao cinza).
                sem, motivo = "cinza", "nao_se_aplica"
            elif not t["aplicavel_por_padrao"]:
                # Sem `and ultima is None`: o historico do par nao transforma um tipo de
                # excecao em exigencia -- so' o cadastro do tipo faz isso (regra 3 do
                # checklist, decisao R15).
                sem, motivo = "cinza", "nao_cobrada"
            else:
                sem = "vermelho"
            out.append({"entidade_id": e["id"], "entidade": e["nome"], "papel": e["papel"],
                        "tipo_id": t["id"], "tipo": t["nome"], "jurisdicao": t["jurisdicao"],
                        "semaforo": sem, "motivo": motivo, "dias": dias, "vigente": v,
                        "ultima": ultima})
    return out
