"""Snapshots do banco, ensaio de restauracao, copia externa diaria e retencao em camadas.

- Snapshot horario (e um no boot) por `VACUUM INTO`, atomico (.tmp + rename), 48 locais.
- Cada snapshot passa por um ENSAIO DE RESTAURACAO: abre-se a copia e roda-se
  `PRAGMA integrity_check`. Snapshot que nao abre e' apagado e contado como falha.
- Copia externa (outro volume ou compartilhamento, `DASH_BACKUP_EXTERNO`): uma vez
  por dia, com `.sha256` ao lado, conferida relendo o destino. Retencao em camadas:
  7 diarios, 5 semanais, 12 mensais.
- Arquivos ao lado do banco (issue #55): `notas`, `espelhos`, `modelos` e `evidencias` vao
  para `<backups>/arquivos/<pasta>/` e, havendo pasta externa, para
  `<externo>/arquivos/<pasta>/`, a cada rodada, depois do snapshot. Os nomes sao o sha256 do
  conteudo e nunca mudam de conteudo: uma copia de cada arquivo serve a todos os
  snapshots (o disco nao cresce 48 vezes) e o backup nunca apaga o que guardou (um
  snapshot antigo pode citar arquivo que ja saiu da pasta de dados).
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
PASTAS_ARQUIVOS = ("notas", "espelhos", "modelos", "evidencias")
SUBPASTA_ARQUIVOS = "arquivos"  # dentro da pasta de backups e da pasta externa

# Ultima rodada, para o health. Datas em ISO local; None = nunca nesta execucao.
ESTADO: dict = {"ultimo_snapshot": None, "ultimo_snapshot_erro": None,
                "ultima_copia_arquivos": None, "ultima_copia_arquivos_erro": None,
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

    antigos = sorted(pasta_destino.glob(PADRAO))
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


# --- arquivos ao lado do banco (issue #55) ---------------------------------------------

def copiar_arquivos(raiz_origem: Path, raiz_destino: Path) -> int:
    """Copia `raiz_origem/<pasta>/*` para `raiz_destino/<pasta>/` nas PASTAS_ARQUIVOS.

    Serve aos dois sentidos: backup (dados -> backups/arquivos) e restauracao
    (backups/arquivos -> dados). So' copia o que falta no destino; nunca apaga nada.
    Temporarios (`*.tmp`, upload em andamento) ficam de fora. Cada copia vai para um
    `.tmp`, e' conferida pelo sha256 contra a origem e so' entao renomeada: ou o
    arquivo aparece inteiro, ou nao aparece. Origem cujo conteudo nao bate com o
    sha256 do proprio nome nao e' copiada (copiaria o defeito para o backup).
    Um arquivo com problema nao impede os outros: todos sao tentados e, no fim, sobe
    um OSError com os que ficaram sem copia. Devolve quantos arquivos copiou.
    """
    copiados = 0
    falhas: list[str] = []
    agora = time.time()
    for nome in PASTAS_ARQUIVOS:
        origem = raiz_origem / nome
        if not origem.is_dir():
            continue
        destino = raiz_destino / nome
        destino.mkdir(parents=True, exist_ok=True)
        _limpar_parciais_abandonados(destino, agora)
        for arquivo in sorted(origem.iterdir()):
            if not arquivo.is_file() or arquivo.name.endswith(".tmp"):
                continue
            try:
                if _copiar_um(arquivo, destino / arquivo.name):
                    copiados += 1
            except OSError as e:
                falhas.append(f"{nome}/{arquivo.name} ({e})")
    if falhas:
        mais = f" e mais {len(falhas) - 3}" if len(falhas) > 3 else ""
        raise OSError(f"{len(falhas)} arquivo(s) sem copia: {'; '.join(falhas[:3])}{mais}")
    return copiados


_PARCIAL_NOSSO = re.compile(r"\.\d+\.tmp$")  # `<nome>.<pid>.tmp`, so' o que _copiar_um cria


def _limpar_parciais_abandonados(destino: Path, agora: float) -> None:
    """Sobra de copia interrompida (processo morto no meio): o PID muda na proxima
    rodada, entao ninguem mais a renomeia. Mesmo corte de 1 hora dos snapshots."""
    for sobra in destino.glob("*.tmp"):
        try:
            if _PARCIAL_NOSSO.search(sobra.name) and agora - sobra.stat().st_mtime > IDADE_TMP_SEG:
                sobra.unlink(missing_ok=True)
        except OSError:
            pass


def _copiar_um(arquivo: Path, alvo: Path) -> bool:
    """Copia um arquivo conferido; False se ja estava la."""
    # o nome e' o sha256 do conteudo: mesmo nome e mesmo tamanho = mesmo arquivo
    if alvo.exists() and alvo.stat().st_size == arquivo.stat().st_size:
        return False
    esperado = _sha256(arquivo)
    if re.fullmatch(r"[0-9a-f]{64}", arquivo.stem) and arquivo.stem != esperado:
        raise OSError("conteudo nao bate com o sha256 do nome")
    parcial = alvo.parent / f"{arquivo.name}.{os.getpid()}.tmp"
    try:
        shutil.copyfile(arquivo, parcial)
        if _sha256(parcial) != esperado:
            raise OSError("sha256 divergente na copia")
        parcial.replace(alvo)
    except BaseException:
        parcial.unlink(missing_ok=True)
        raise
    return True


def _copiou_hoje(pasta_externa: Path, hoje: datetime.date) -> bool:
    """So conta o dia como feito com o par .db + .sha256 (o .sha256 e' gravado por
    ultimo: sem ele, a copia pode ter morrido no meio e a proxima rodada refaz)."""
    if not pasta_externa.exists():
        return False
    return any(_data_do_nome(a) == hoje and (pasta_externa / f"{a.name}.sha256").exists()
               for a in pasta_externa.glob(PADRAO))


# --- rodada e agendamento ------------------------------------------------------------

def rodada(origem_db: Path, pasta_destino: Path, pasta_externa: Path | None) -> None:
    """Uma rodada completa: snapshot + ensaio; arquivos (local e externo); copia externa
    do banco se ainda nao houve hoje."""
    agora = tempo.para_local(tempo.agora_utc())
    snapshot = None
    try:
        snapshot = criar_snapshot(origem_db, pasta_destino)
        ESTADO["ultimo_snapshot"] = agora.isoformat(timespec="seconds")
        ESTADO["ultimo_snapshot_erro"] = None
    except Exception as e:
        ESTADO["ultimo_snapshot_erro"] = f"{agora.isoformat(timespec='seconds')}: {e}"
        log.exception("snapshot falhou")
    # Arquivos DEPOIS do snapshot: todo arquivo que ele cita ja estava no disco (o sistema
    # grava o arquivo antes da linha do banco), entao a copia o alcanca. Copiam mesmo se o
    # snapshot falhou (nao dependem dele), e para fora a cada rodada (so' o que falta), antes
    # da copia externa do banco: o snapshot que sai hoje encontra do outro lado o que cita.
    destinos = [("", pasta_destino / SUBPASTA_ARQUIVOS)]
    if pasta_externa is not None:
        destinos.append(("copia externa: ", pasta_externa / SUBPASTA_ARQUIVOS))
    erros = []
    for rotulo, destino in destinos:
        try:
            copiar_arquivos(origem_db.parent, destino)
        except Exception as e:
            erros.append(f"{rotulo}{e}")
            log.exception("copia dos arquivos falhou (%s)", destino)
    if erros:
        ESTADO["ultima_copia_arquivos_erro"] = f"{agora.isoformat(timespec='seconds')}: {'; '.join(erros)}"
    else:
        ESTADO["ultima_copia_arquivos"] = agora.isoformat(timespec="seconds")
        ESTADO["ultima_copia_arquivos_erro"] = None
    if pasta_externa is None or snapshot is None:
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
