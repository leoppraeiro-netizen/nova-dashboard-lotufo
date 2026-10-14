"""Entidades juridicas do grupo: a Lotufo, os consorcios e as consorciadas (spec §5).

Habilitacao e' verificada POR CNPJ -- o orgao cobra a certidao do consorcio E a de cada
consorciada -- entao certidoes e dividas penduram na entidade, nao numa "empresa" unica.

Desativar e' SOFT (ativo=0): a entidade sai dos paineis mas o historico de certidoes que
ela portava continua respondendo "o que valia no dia do protocolo X".
"""
import re
import sqlite3

from app import auditoria, db

PAPEIS = ("lotufo", "consorcio", "consorciada")


def _digitos(cnpj) -> str:
    return re.sub(r"\D", "", cnpj or "")


# `cnpj_valido` e' PUBLICA (nao `_cnpj_valido`) porque a validacao de CNPJ deixou de
# ser assunto so' do cadastro: a leitura de certidao (app/leitura_pdf.py) confere o DV
# do CNPJ que a regex achou no PDF antes de sugeri-lo. Uma segunda implementacao la
# divergiria desta no primeiro ajuste de regra da Receita.


def cnpj_valido(cnpj: str) -> bool:
    """DV padrao da Receita: modulo 11 com pesos 2..9 ciclicos, da direita para a esquerda.

    Recebe ja normalizado (so digitos) -- quem normaliza e' `_digitos`.
    """
    if len(cnpj) != 14 or not cnpj.isdigit():
        return False
    # 00000000000000, 11111111111111, ... satisfazem o modulo 11 (soma multipla de 11 ou
    # resto < 2) e nao sao CNPJ de ninguem. Sem esta guarda, o digitador que segura uma
    # tecla cadastra uma entidade fantasma que passa em toda a validacao seguinte.
    if cnpj == cnpj[0] * 14:
        return False
    for tamanho in (12, 13):     # 1o DV sobre os 12 primeiros; 2o sobre os 13
        soma = 0
        peso = 2
        for d in reversed(cnpj[:tamanho]):
            soma += int(d) * peso
            peso = 2 if peso == 9 else peso + 1
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(cnpj[tamanho]):
            return False
    return True


def criar(conn: sqlite3.Connection, usuario_id: int, dados: dict) -> int:
    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise ValueError("Nome da entidade é obrigatório")
    papel = dados.get("papel")
    if papel not in PAPEIS:
        raise ValueError(f"Papel inválido: {papel} (use 'lotufo', 'consorcio' ou 'consorciada')")
    # Normalizar para 14 digitos ANTES de validar e gravar: a unicidade e' sobre o numero,
    # nao sobre a mascara digitada -- senao "11.444.777/0001-61" e "11444777000161" viram
    # duas entidades para o mesmo CNPJ e o painel de certidoes duplica a linha.
    cnpj = _digitos(dados.get("cnpj"))
    if not cnpj_valido(cnpj):
        raise ValueError(f"CNPJ inválido: {dados.get('cnpj')!r}")
    duplicado = f"CNPJ {cnpj} já cadastrado para outra entidade"
    coligada = dados.get("coligada_rm")
    if coligada is not None and (isinstance(coligada, bool) or not isinstance(coligada, int) or coligada < 0):
        raise ValueError("Coligada do RM deve ser um inteiro não negativo")
    with db.mutacao(conn):
        if conn.execute("SELECT id FROM entidades WHERE cnpj=?", (cnpj,)).fetchone():
            raise ValueError(duplicado)
        # O SELECT acima e' cortesia (mensagem boa no caso comum); quem decide e' o UNIQUE
        # do schema -- entre a leitura e o INSERT outra requisicao pode inserir o mesmo CNPJ.
        try:
            cur = conn.execute("INSERT INTO entidades (nome, cnpj, papel, coligada_rm) VALUES (?,?,?,?)",
                               (nome, cnpj, papel, coligada))
        except sqlite3.IntegrityError as e:
            # So a violacao de unicidade vira erro de dominio: CHECK/FK quebrados sao bug
            # nosso e devem continuar subindo (nao mentir dizendo "ja cadastrado").
            if "UNIQUE" not in str(e).upper():
                raise
            if "coligada" in str(e).lower():
                raise ValueError(f"Coligada {coligada} já pertence a outra entidade") from e
            raise ValueError(duplicado) from e
        eid = cur.lastrowid
        auditoria.registrar(conn, usuario_id, "entidade.criar", "entidade", eid, None,
                            {"nome": nome, "cnpj": cnpj, "papel": papel, "coligada_rm": coligada})
    return eid


def definir_coligada(conn: sqlite3.Connection, usuario_id: int, entidade_id: int, coligada) -> None:
    """Qual coligada do RM emite as NFs desta entidade (fase 5). None desliga o casamento."""
    if coligada is not None and (isinstance(coligada, bool) or not isinstance(coligada, int) or coligada < 0):
        raise ValueError("Coligada do RM deve ser um inteiro não negativo")
    with db.mutacao(conn):
        e = detalhe(conn, entidade_id)
        if e is None:
            raise ValueError(f"Entidade {entidade_id} não encontrada")
        try:
            conn.execute("UPDATE entidades SET coligada_rm=? WHERE id=?", (coligada, entidade_id))
        except sqlite3.IntegrityError as e:
            if "UNIQUE" not in str(e).upper():
                raise
            raise ValueError(f"Coligada {coligada} já pertence a outra entidade") from e
        auditoria.registrar(conn, usuario_id, "entidade.coligada_rm", "entidade", entidade_id,
                            {"coligada_rm": e["coligada_rm"]}, {"coligada_rm": coligada})


def detalhe(conn: sqlite3.Connection, entidade_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM entidades WHERE id=?", (entidade_id,)).fetchone()
    return dict(r) if r else None


def listar(conn: sqlite3.Connection, ativas: bool = True) -> list[dict]:
    sql = "SELECT * FROM entidades"
    if ativas:
        sql += " WHERE ativo=1"
    return [dict(r) for r in conn.execute(sql + " ORDER BY papel, nome, id")]


def desativar(conn: sqlite3.Connection, usuario_id: int, entidade_id: int) -> None:
    with db.mutacao(conn):
        e = detalhe(conn, entidade_id)
        if e is None:
            raise ValueError(f"Entidade {entidade_id} não encontrada")
        if not e["ativo"]:
            raise ValueError(f"Entidade {e['nome']} já está desativada")
        # Contrato ativo aponta para a entidade que se habilita por ele: desativada, ela
        # some de `listar` -- e some do painel de certidoes e do checklist de protocolo,
        # que percorrem as entidades ATIVAS. O contrato continuaria vivo cobrando
        # certidoes de um CNPJ que a tela nao mostra mais; a pendencia so' apareceria na
        # sessao do orgao. COALESCE p/ 1: contrato gravado antes da migracao 009 tem
        # entidade NULL e e' da Lotufo (mesma leitura de `contratos.entidade_de`).
        # SQL aqui, e nao `paineis`: este modulo nao depende de painel para saber que
        # nao pode se apagar.
        ativo = conn.execute("SELECT numero_instrumento FROM contratos "
                             "WHERE COALESCE(entidade_id,1)=? AND estado='ativo' LIMIT 1",
                             (entidade_id,)).fetchone()
        if ativo is not None:
            raise ValueError(f"Entidade {e['nome']} tem contrato ativo "
                             f"({ativo['numero_instrumento']}); mude o contrato de "
                             f"entidade antes de desativá-la")
        # `AND ativo=1`: a desativacao so vale a partir do estado que foi lido. Sem a
        # condicao, duas requisicoes concorrentes gravariam DUAS linhas de auditoria
        # dizendo 1 -> 0 para uma mudanca que aconteceu uma vez so.
        cur = conn.execute("UPDATE entidades SET ativo=0 WHERE id=? AND ativo=1", (entidade_id,))
        if cur.rowcount != 1:
            raise ValueError("Entidade desativada concorrentemente; tente novamente")
        auditoria.registrar(conn, usuario_id, "entidade.desativar", "entidade", entidade_id,
                            {"ativo": 1}, {"ativo": 0})
