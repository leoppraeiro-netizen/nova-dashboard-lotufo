import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app import auditoria, db

_ph = PasswordHasher()
MAX_FALHAS = 5
BLOQUEIO_MIN = 15
SESSAO_HORAS = 12
SENHA_MIN = 10  # mesma regra da criacao de usuario (api_usuarios)

# Hash descartavel, gerado uma vez na importacao do modulo. Serve para que os
# caminhos "e-mail nao existe" e "usuario bloqueado" gastem o mesmo tempo de um
# verify real -- sem ele, a diferenca (~0,06ms vs ~135ms) entrega quais e-mails
# estao cadastrados.
_HASH_DUMMY = _ph.hash("hash-dummy-para-tempo-uniforme")

def _agora() -> datetime:
    return datetime.now(timezone.utc)

def _verify_dummy(senha: str) -> None:
    """Queima o tempo de um verify argon2 e ignora o resultado."""
    try:
        _ph.verify(_HASH_DUMMY, senha)
    except VerificationError:
        pass

def criar_usuario(conn: sqlite3.Connection, nome: str, email: str, senha: str, perfil: str) -> int:
    # _ph.hash e' caro (~135ms) e nao toca no banco: sai de dentro do bloco para nao
    # segurar o lock de escrita durante o hash. (Quando o chamador ja abriu a
    # transacao -- POST /api/admin/usuarios, que precisa do mesmo commit da
    # auditoria -- o lock e' dele e o hash cai dentro; e' rota de admin, rara.)
    senha_hash = _ph.hash(senha)
    with db.mutacao(conn):
        cur = conn.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (?,?,?,?)",
            (nome, email.lower(), senha_hash, perfil))
    return cur.lastrowid

def autenticar(conn: sqlite3.Connection, email: str, senha: str) -> dict | None:
    row = conn.execute("SELECT * FROM usuarios WHERE email=? AND ativo=1",
                       (email.lower(),)).fetchone()
    if row is None:
        _verify_dummy(senha)
        return None
    if row["bloqueado_ate"] and datetime.fromisoformat(row["bloqueado_ate"]) > _agora():
        _verify_dummy(senha)
        return None
    try:
        _ph.verify(row["senha_hash"], senha)
    except VerifyMismatchError:
        # autenticar() e' caminho de LEITURA que muta o contador de lockout: so o
        # UPDATE entra em transacao, e ela fecha aqui. Nao ha auditoria neste passo
        # (quem audita login/login_falha e' a rota, na transacao dela).
        # A-06 (10/10/2026): o incremento e' feito PELO BANCO, sob o BEGIN IMMEDIATE, e o valor
        # novo e' relido no mesmo envelope. Antes gravava-se "lido la' em cima + 1": 10 tentativas
        # simultaneas gravavam 1 e o bloqueio nunca chegava.
        with db.mutacao(conn):
            conn.execute("UPDATE usuarios SET tentativas_falhas = tentativas_falhas + 1 WHERE id=?", (row["id"],))
            falhas = conn.execute("SELECT tentativas_falhas FROM usuarios WHERE id=?",
                                  (row["id"],)).fetchone()["tentativas_falhas"]
            if falhas >= MAX_FALHAS:
                conn.execute("UPDATE usuarios SET tentativas_falhas=0, bloqueado_ate=? WHERE id=?",
                             ((_agora() + timedelta(minutes=BLOQUEIO_MIN)).isoformat(), row["id"]))
        return None
    except InvalidHashError:
        # senha_hash corrompido/invalido: problema de dado, nao senha errada.
        # Nao incrementa o contador nem expoe detalhe ao chamador.
        return None
    with db.mutacao(conn):
        # A-06: o bloqueio pode ter sido gravado por uma tentativa simultanea enquanto esta
        # conferia a senha (a leitura la' em cima e' anterior). Bloqueada agora = recusa, sem zerar.
        ate = conn.execute("SELECT bloqueado_ate FROM usuarios WHERE id=?", (row["id"],)).fetchone()["bloqueado_ate"]
        if ate and datetime.fromisoformat(ate) > _agora():
            return None
        conn.execute("UPDATE usuarios SET tentativas_falhas=0, bloqueado_ate=NULL WHERE id=?",
                     (row["id"],))
    return dict(row)

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def criar_sessao(conn: sqlite3.Connection, usuario_id: int) -> tuple[str, str]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    expira = (_agora() + timedelta(hours=SESSAO_HORAS)).isoformat()
    with db.mutacao(conn):
        conn.execute("INSERT INTO sessoes (token_hash, usuario_id, csrf_token, expira_em) VALUES (?,?,?,?)",
                     (_hash_token(token), usuario_id, csrf, expira))
    return token, csrf

def sessao_valida(conn: sqlite3.Connection, token: str) -> dict | None:
    row = conn.execute("SELECT * FROM sessoes WHERE token_hash=?", (_hash_token(token),)).fetchone()
    if row is None or datetime.fromisoformat(row["expira_em"]) < _agora():
        return None
    return dict(row)

def encerrar_sessao(conn: sqlite3.Connection, token: str) -> None:
    with db.mutacao(conn):
        conn.execute("DELETE FROM sessoes WHERE token_hash=?", (_hash_token(token),))


# A-05/B-10 (10/10/2026): conta trancada so' destravava sozinha em 15 min ou por SQL no banco, e
# senha so' se trocava recriando o usuario. Erro de regra sobe como ValueError (a rota vira 422) e
# usuario inexistente como LookupError (404). Cada funcao e' dona da propria transacao, com a
# auditoria no mesmo commit, e a senha nunca vai para a auditoria.

def _usuario(conn: sqlite3.Connection, usuario_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT id, email, tentativas_falhas, bloqueado_ate FROM usuarios WHERE id=?",
                       (usuario_id,)).fetchone()
    if row is None:
        raise LookupError("Usuário não encontrado")
    return row

def _conferir_tamanho(nova: str) -> None:
    if len(nova) < SENHA_MIN:
        raise ValueError(f"Senha deve ter no mínimo {SENHA_MIN} caracteres")

def desbloquear(conn: sqlite3.Connection, admin_id: int | None, usuario_id: int) -> None:
    with db.mutacao(conn):
        row = _usuario(conn, usuario_id)
        conn.execute("UPDATE usuarios SET tentativas_falhas=0, bloqueado_ate=NULL WHERE id=?", (usuario_id,))
        auditoria.registrar(conn, admin_id, "usuario.desbloquear", "usuario", str(usuario_id),
                            antes={"tentativas_falhas": row["tentativas_falhas"], "bloqueado_ate": row["bloqueado_ate"]})

def redefinir_senha(conn: sqlite3.Connection, admin_id: int | None, usuario_id: int, nova: str) -> None:
    """Senha nova dada pelo admin: zera o bloqueio e derruba TODAS as sessoes do usuario (quem
    estava logado com a senha antiga, inclusive um invasor, sai)."""
    _conferir_tamanho(nova)
    _usuario(conn, usuario_id)
    senha_hash = _ph.hash(nova)  # caro e sem banco: fora do lock de escrita
    with db.mutacao(conn):
        _usuario(conn, usuario_id)
        conn.execute("UPDATE usuarios SET senha_hash=?, tentativas_falhas=0, bloqueado_ate=NULL WHERE id=?",
                     (senha_hash, usuario_id))
        conn.execute("DELETE FROM sessoes WHERE usuario_id=?", (usuario_id,))
        auditoria.registrar(conn, admin_id, "usuario.senha_redefinida", "usuario", str(usuario_id))

def trocar_senha(conn: sqlite3.Connection, usuario_id: int, atual: str, nova: str, token_atual: str) -> None:
    """O proprio usuario troca a senha. A atual passa pelo MESMO verificador do login (`autenticar`):
    errar aqui conta para o bloqueio, senao uma sessao roubada viraria um chute de senha sem limite.
    As outras sessoes do usuario caem; a atual (token_atual) continua."""
    _conferir_tamanho(nova)
    if nova == atual:
        raise ValueError("A senha nova tem que ser diferente da atual")
    # Gate Sol S1 (10/10/2026): o hash observado ANTES de conferir a atual. Entre a conferencia e a gravacao
    # roda o Argon2; se nesse meio-tempo o admin redefinir a senha (e derrubar as sessoes), a troca nao pode
    # gravar por cima: exige a sessao ainda viva e o hash ainda igual ao observado.
    observado = conn.execute("SELECT senha_hash FROM usuarios WHERE id=?", (usuario_id,)).fetchone()
    if autenticar(conn, _usuario(conn, usuario_id)["email"], atual) is None:
        raise ValueError("Senha atual não confere")
    senha_hash = _ph.hash(nova)
    with db.mutacao(conn):
        if conn.execute("SELECT 1 FROM sessoes WHERE token_hash=? AND usuario_id=?",
                        (_hash_token(token_atual), usuario_id)).fetchone() is None:
            raise ValueError("Sua sessão foi encerrada: entre de novo")
        if conn.execute("UPDATE usuarios SET senha_hash=? WHERE id=? AND senha_hash=?",
                        (senha_hash, usuario_id, observado["senha_hash"])).rowcount != 1:
            raise ValueError("A senha mudou enquanto você trocava: entre de novo com a senha atual")
        conn.execute("DELETE FROM sessoes WHERE usuario_id=? AND token_hash<>?", (usuario_id, _hash_token(token_atual)))
        auditoria.registrar(conn, usuario_id, "usuario.senha_trocada", "usuario", str(usuario_id))
