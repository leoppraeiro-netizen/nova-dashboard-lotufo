"""Snapshots do banco, ensaio de restauracao, copia externa diaria e retencao em camadas.

- Snapshot horario (e um no boot) por `VACUUM INTO`, atomico (.tmp + rename), 48 locais.
- Cada snapshot passa por um ENSAIO DE RESTAURACAO: abre-se a copia e roda-se
  `PRAGMA integrity_check`. Snapshot que nao abre e' apagado e contado como falha.
- Copia externa (outro volume ou compartilhamento, `DASH_BACKUP_EXTERNO`): uma vez
  por dia, com `.sha256` ao lado, conferida relendo o destino. Retencao em camadas:
  7 diarios, 5 semanais, 12 mensais.
- `ESTADO` guarda o resultado da ultima rodada; /api/health o expoe.
"""

import datetime
import hashlib
import logging
import os
import re
import shutil
import sqlite3
import threading
import time
from pathlib import Path

from app import tempo

log = logging.getLogger("app.backup")

MANTER = 48  # ~2 dias de snapshots horarios
PADRAO = "dashboard-*.db"  # o que a rotacao enxerga (nao casa com *.db.tmp)
IDADE_TMP_SEG = 3600  # so e' "sobra" o .tmp que ja passou de 1 hora
_NOME = re.compile(r"dashboard-(\d{4})(\d{2})(\d{2})-\d{6}\.db$")
CAMADAS = {"diarios": 7, "semanais": 5, "mensais": 12}

# Ultima rodada, para o health. Datas em ISO local; None = nunca nesta execucao.
ESTADO: dict = {"ultimo_snapshot": None, "ultimo_snapshot_erro": None,
                "ultima_copia_externa": None, "ultima_copia_externa_erro": None}


class SnapshotInvalido(Exception):
    pass


def _limpar_tmp_abandonados(pasta_destino: Path, agora: float) -> None:
    """Remove SO os .tmp velhos o bastante para nao serem de ninguem vivo.

    Dois processos podem escrever snapshots na mesma pasta (a tarefa agendada e
    uma execucao manual, por exemplo). Apagar todo *.db.tmp no inicio destruiria
    o VACUUM em andamento do outro processo, que so descobriria isso no rename
    final. O corte por mtime resolve: .tmp com mais de 1h e' sobra de processo
    morto; um recem-criado pertence a alguem que ainda esta trabalhando.
    """
    for sobra in pasta_destino.glob("*.db.tmp"):
        try:
            if agora - sobra.stat().st_mtime > IDADE_TMP_SEG:
                sobra.unlink(missing_ok=True)
        except OSError:
            pass  # sumiu/travou no meio (outro processo renomeou): nao e' problema nosso


def verificar_snapshot(arquivo: Path) -> None:
    """Ensaio de restauracao: o snapshot abre e passa no integrity_check.

    E' o que o runbook manda fazer ao restaurar; fazer a cada snapshot garante que o
    backup que sera' usado no pior dia ja foi aberto pelo menos uma vez.
    """
    try:
        conn = sqlite3.connect(f"file:{arquivo}?mode=ro", uri=True)
        try:
            r = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
    except sqlite3.Error as e:
        raise SnapshotInvalido(f"{arquivo.name}: nao abre ({e})") from e
    if r is None or r[0] != "ok":
        raise SnapshotInvalido(f"{arquivo.name}: integrity_check = {r[0] if r else None!r}")


def criar_snapshot(origem_db: Path, pasta_destino: Path) -> Path:
    pasta_destino.mkdir(parents=True, exist_ok=True)

    _limpar_tmp_abandonados(pasta_destino, time.time())

    # Carimbo na hora de CUIABA, nao no relogio da maquina: e' o nome pelo qual alguem
    # procura "o backup de ontem de manha", e a rotacao ordena por ele. `datetime.now()`
    # sem fuso mudava de significado com o servidor (a proibicao esta em app/tempo.py).
    carimbo = f"{tempo.para_local(tempo.agora_utc()):%Y%m%d-%H%M%S}"
    nome = f"dashboard-{carimbo}.db"
    destino = pasta_destino / nome
    # Escrever num nome que a rotacao NAO enxerga e so entao renomear: se o
    # VACUUM morrer no meio, o arquivo parcial nunca conta como snapshot valido
    # nem empurra um backup bom para fora da janela de 48.
    # O PID entra no nome do temporario para que dois processos concorrentes
    # nunca escrevam no MESMO arquivo parcial (um sobrescreveria o VACUUM do outro).
    parcial = pasta_destino / f"dashboard-{carimbo}-pid{os.getpid()}.db.tmp"
    conn = sqlite3.connect(origem_db)
    try:
        conn.execute("VACUUM INTO ?", (str(parcial),))
    except BaseException:
        parcial.unlink(missing_ok=True)
        raise
    finally:
        conn.close()
    # Ensaio ANTES do rename: um parcial que nao passa nunca vira snapshot valido.
    try:
        verificar_snapshot(parcial)
    except SnapshotInvalido:
        parcial.unlink(missing_ok=True)
        raise
    parcial.replace(destino)  # rename atomico no mesmo volume

    # So os horarios (dashboard-AAAAMMDD-HHMMSS.db): os PRE-* nao entram na conta nem sao apagados.
    antigos = sorted(a for a in pasta_destino.glob(PADRAO) if _NOME.match(a.name))
    for velho in antigos[:-MANTER] if len(antigos) > MANTER else []:
        velho.unlink()
    return destino


# --- copia externa -----------------------------------------------------------------

def _sha256(arquivo: Path) -> str:
    h = hashlib.sha256()
    with open(arquivo, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _data_do_nome(arquivo: Path) -> datetime.date | None:
    m = _NOME.match(arquivo.name)
    return datetime.date(int(m[1]), int(m[2]), int(m[3])) if m else None


def copiar_externo(snapshot: Path, pasta_externa: Path) -> Path:
    """Copia o snapshot para fora com checksum conferido no destino.

    Escreve `.tmp` + rename e grava `<nome>.sha256`; depois RELE o destino e compara
    -- a copia so conta quando o que esta no outro volume e' o que saiu daqui.
    """
    pasta_externa.mkdir(parents=True, exist_ok=True)
    esperado = _sha256(snapshot)
    destino = pasta_externa / snapshot.name
    parcial = pasta_externa / f"{snapshot.name}.tmp"
    try:
        shutil.copyfile(snapshot, parcial)
        if _sha256(parcial) != esperado:
            raise OSError(f"checksum divergente ao copiar {snapshot.name} para {pasta_externa}")
        parcial.replace(destino)
    except BaseException:
        parcial.unlink(missing_ok=True)
        raise
    (pasta_externa / f"{snapshot.name}.sha256").write_text(f"{esperado}  {snapshot.name}\n",
                                                           encoding="utf-8")
    rotacionar_externo(pasta_externa)
    return destino


def rotacionar_externo(pasta_externa: Path) -> None:
    """Retencao em camadas: o mais novo de cada dia (7), semana ISO (5) e mes (12).

    Um arquivo fica se cabe em QUALQUER camada. Com uma copia por dia, o diario e'
    o proprio arquivo; o semanal e o mensal sao o ultimo de cada periodo.
    """
    arquivos = [(d, a) for a in pasta_externa.glob(PADRAO) if (d := _data_do_nome(a))]
    arquivos.sort(key=lambda par: (par[0], par[1].name))
    manter: set[Path] = set()
    for chave, quantos in ((lambda d: d, CAMADAS["diarios"]),
                           (lambda d: d.isocalendar()[:2], CAMADAS["semanais"]),
                           (lambda d: (d.year, d.month), CAMADAS["mensais"])):
        ultimo_por_periodo: dict = {}
        for d, a in arquivos:
            ultimo_por_periodo[chave(d)] = a  # ordenado: o ultimo visto e' o mais novo
        for periodo in sorted(ultimo_por_periodo)[-quantos:]:
            manter.add(ultimo_por_periodo[periodo])
    for _, a in arquivos:
        if a not in manter:
            a.unlink(missing_ok=True)
            (pasta_externa / f"{a.name}.sha256").unlink(missing_ok=True)


def _copiou_hoje(pasta_externa: Path, hoje: datetime.date) -> bool:
    """So conta o dia como feito com o par .db + .sha256 (o .sha256 e' gravado por
    ultimo: sem ele, a copia pode ter morrido no meio e a proxima rodada refaz)."""
    if not pasta_externa.exists():
        return False
    return any(_data_do_nome(a) == hoje and (pasta_externa / f"{a.name}.sha256").exists()
               for a in pasta_externa.glob(PADRAO))


# --- rodada e agendamento ------------------------------------------------------------

def rodada(origem_db: Path, pasta_destino: Path, pasta_externa: Path | None) -> None:
    """Uma rodada completa: snapshot + ensaio; copia externa se ainda nao houve hoje."""
    agora = tempo.para_local(tempo.agora_utc())
    try:
        snapshot = criar_snapshot(origem_db, pasta_destino)
        ESTADO["ultimo_snapshot"] = agora.isoformat(timespec="seconds")
        ESTADO["ultimo_snapshot_erro"] = None
    except Exception as e:
        ESTADO["ultimo_snapshot_erro"] = f"{agora.isoformat(timespec='seconds')}: {e}"
        log.exception("snapshot falhou")
        return
    if pasta_externa is None:
        return
    try:
        # `exists()`/`glob()` num compartilhamento sem permissao levantam PermissionError
        # (pathlib so engole ENOENT): tem que estar DENTRO do try, senao a thread morre
        # calada e o health segue dizendo "sem erro" para sempre.
        if _copiou_hoje(pasta_externa, agora.date()):
            return
        copiar_externo(snapshot, pasta_externa)
        ESTADO["ultima_copia_externa"] = agora.isoformat(timespec="seconds")
        ESTADO["ultima_copia_externa_erro"] = None
    except Exception as e:
        ESTADO["ultima_copia_externa_erro"] = f"{agora.isoformat(timespec='seconds')}: {e}"
        log.exception("copia externa falhou")


def pasta_local() -> Path:
    """Onde ficam os snapshots: ao lado do banco (nunca dependem do diretorio de trabalho)."""
    from app import db
    return db.db_path().parent / "backups"


def pasta_externa() -> Path | None:
    """A copia externa diaria, se `DASH_BACKUP_EXTERNO` estiver configurada."""
    externo = os.environ.get("DASH_BACKUP_EXTERNO")
    return Path(externo) if externo else None


# Snapshot e' horario: passou de 2 h sem um novo, uma rodada inteira falhou ou a thread parou.
ATRASO_MAX = datetime.timedelta(hours=2)


def _snapshots_locais(local: Path) -> list[os.stat_result]:
    """stat de cada snapshot HORARIO guardado (nome `dashboard-AAAAMMDD-HHMMSS.db`). O
    `dashboard-PRE-*.db` do deploy casa com PADRAO mas nao e' a rotina horaria: contado, um
    deploy recente esconderia o snapshot horario parado. Arquivo que some no meio (a rotacao do
    outro processo) fica de fora; pasta ilegivel conta como vazia, e a tela mostra o atraso."""
    stats = []
    try:
        arquivos = [a for a in local.glob(PADRAO) if _NOME.match(a.name)] if local.exists() else []
    except OSError:
        return []
    for a in arquivos:
        try:
            stats.append(a.stat())
        except OSError:
            pass
    return stats


def _erro_para_tela(bruto: str | None, mensagem: str) -> tuple[str | None, str | None]:
    """`ESTADO` guarda "<iso>: <excecao>", e a excecao traz caminho, compartilhamento e maquina.
    A tela recebe so' o momento e uma frase fixa; o detalhe fica no log do servidor (`log.exception`)."""
    if not bruto:
        return None, None
    em = bruto.split(": ", 1)[0]  # o ISO nao tem ": " (so' ":" sem espaco)
    return em, f"{mensagem}; o detalhe está no log do servidor"


def situacao(local: Path, externa_configurada: bool, agora: datetime.datetime) -> dict:
    """Saude do backup para a tela de Administracao (issue #31).

    O ultimo backup e a contagem vem do DISCO (sobrevivem ao servidor reiniciar); os erros
    vem de `ESTADO`, que so existe na memoria desta execucao. Sem snapshot nenhum conta como
    atrasado: backup parado sem ninguem ver e' o risco que a tela existe para mostrar.
    A pasta externa NAO e' lida aqui: um compartilhamento fora do ar travaria a tela.
    """
    stats = _snapshots_locais(local)
    ultimo = max(stats, key=lambda s: s.st_mtime) if stats else None
    ultimo_em = datetime.datetime.fromtimestamp(ultimo.st_mtime, datetime.timezone.utc) if ultimo else None
    snap_erro_em, snap_erro = _erro_para_tela(ESTADO["ultimo_snapshot_erro"], "não foi possível gravar o snapshot")
    copia_erro_em, copia_erro = _erro_para_tela(ESTADO["ultima_copia_externa_erro"],
                                                "não foi possível fazer a cópia externa")
    return {
        "ultimo_snapshot": ESTADO["ultimo_snapshot"],
        "ultimo_snapshot_erro": snap_erro,
        "ultimo_snapshot_erro_em": snap_erro_em,
        "ultima_copia_externa": ESTADO["ultima_copia_externa"],
        "ultima_copia_externa_erro": copia_erro,
        "ultima_copia_externa_erro_em": copia_erro_em,
        "ultimo_backup": tempo.para_local(ultimo_em).isoformat(timespec="seconds") if ultimo_em else None,
        "tamanho_bytes": ultimo.st_size if ultimo else None,
        "guardados": len(stats),
        "copia_externa_configurada": externa_configurada,
        "atrasado": ultimo_em is None or agora - ultimo_em > ATRASO_MAX,
    }


def agendar_backup_horario(origem_db: Path, pasta_destino: Path,
                           pasta_externa: Path | None = None) -> threading.Thread:
    def loop():
        while True:  # primeira rodada no boot, nao uma hora depois
            try:
                rodada(origem_db, pasta_destino, pasta_externa)
            except Exception:  # rede de seguranca: a thread de backup nunca morre
                log.exception("rodada de backup falhou fora do previsto")
            time.sleep(3600)
    t = threading.Thread(target=loop, daemon=True, name="backup")
    t.start()
    return t
