import hashlib
import os
import sqlite3
import time

import pytest

from app import backup

def test_snapshot_e_rotacao(tmp_path):
    origem = tmp_path / "app.db"
    conn = sqlite3.connect(origem)
    conn.execute("CREATE TABLE t (x)"); conn.execute("INSERT INTO t VALUES (42)")
    conn.commit(); conn.close()
    destino = tmp_path / "backups"
    arq = backup.criar_snapshot(origem, destino)
    assert arq.exists()
    check = sqlite3.connect(arq)
    assert check.execute("SELECT x FROM t").fetchone()[0] == 42  # backup abre e tem os dados
    check.close()

def test_rotacao_mantem_48(tmp_path):
    origem = tmp_path / "app.db"
    sqlite3.connect(origem).execute("CREATE TABLE t (x)")
    destino = tmp_path / "backups"; destino.mkdir()
    for i in range(50):
        (destino / f"dashboard-20260101-{i:06d}.db").write_bytes(b"velho")
    backup.criar_snapshot(origem, destino)
    assert len(list(destino.glob("dashboard-*.db"))) == 48


# --- snapshot atomico (revisao final: parcial nao pode expulsar backup bom) ----

def test_tmp_nao_conta_na_rotacao_e_e_limpo(tmp_path):
    # sobra de um processo morto no meio do VACUUM: nao pode contar como snapshot
    # (empurraria um backup bom para fora dos 48) nem ficar para sempre no disco.
    origem = tmp_path / "app.db"
    sqlite3.connect(origem).execute("CREATE TABLE t (x)")
    destino = tmp_path / "backups"; destino.mkdir()
    for i in range(47):
        (destino / f"dashboard-20260101-{i:06d}.db").write_bytes(b"velho")
    sobra = destino / "dashboard-20260101-999999-pid1.db.tmp"
    sobra.write_bytes(b"parcial")
    envelhecer(sobra, 7200)  # 2h: ninguem vivo escreveu isso

    backup.criar_snapshot(origem, destino)

    assert not sobra.exists()                                    # limpo no inicio
    assert list(destino.glob("*.db.tmp")) == []                  # nada pendente no fim
    assert len(list(destino.glob("dashboard-*.db"))) == 48       # 47 antigos + 1 novo
    assert (destino / "dashboard-20260101-000000.db").exists()   # o mais velho sobreviveu


# --- concorrencia entre processos (gate C) ------------------------------------

def envelhecer(caminho, segundos):
    antigo = time.time() - segundos
    os.utime(caminho, (antigo, antigo))

def test_tmp_recente_de_outro_processo_sobrevive(tmp_path):
    # o .tmp fresco pertence a um VACUUM em andamento de OUTRO processo (a tarefa
    # agendada e uma execucao manual dividem a pasta). Apaga-lo destruiria aquele
    # backup, que so descobriria a perda no rename final.
    origem = tmp_path / "app.db"
    sqlite3.connect(origem).execute("CREATE TABLE t (x)")
    destino = tmp_path / "backups"; destino.mkdir()
    vivo = destino / "dashboard-20260101-120000-pid4242.db.tmp"
    vivo.write_bytes(b"vacuum em andamento")

    backup.criar_snapshot(origem, destino)

    assert vivo.exists(), "o .tmp recente de outro processo foi apagado"
    assert vivo.read_bytes() == b"vacuum em andamento"

def test_tmp_leva_o_pid_no_nome(tmp_path, monkeypatch):
    # dois processos com o mesmo carimbo de segundo nao podem escrever no MESMO
    # arquivo parcial: o PID e' o que os separa.
    origem = tmp_path / "app.db"
    sqlite3.connect(origem).execute("CREATE TABLE t (x)")
    destino = tmp_path / "backups"

    vistos = []
    real_connect = sqlite3.connect

    class Espia:
        def __init__(self, c): self._c = c
        def execute(self, sql, params=()):
            if params:
                vistos.append(params[0])
            return self._c.execute(sql, params)
        def close(self): self._c.close()

    monkeypatch.setattr(backup.sqlite3, "connect", lambda *a, **kw: Espia(real_connect(*a, **kw)))
    backup.criar_snapshot(origem, destino)

    assert vistos and vistos[0].endswith(f"-pid{os.getpid()}.db.tmp"), vistos

def test_vacuum_falho_nao_deixa_snapshot(tmp_path, monkeypatch):
    # VACUUM interrompido: o arquivo parcial e removido e nenhum snapshot aparece
    # com nome valido -- a rotacao nunca ve um backup quebrado.
    origem = tmp_path / "app.db"
    sqlite3.connect(origem).execute("CREATE TABLE t (x)")
    destino = tmp_path / "backups"; destino.mkdir()

    real_connect = sqlite3.connect

    class ConnQuebrada:
        def __init__(self, c): self._c = c
        def execute(self, *a, **kw):
            self._c.execute("SELECT 1")  # so para provar que a conexao e usada
            raise KeyboardInterrupt("processo morto no meio do VACUUM")
        def close(self): self._c.close()

    monkeypatch.setattr(backup.sqlite3, "connect", lambda *a, **kw: ConnQuebrada(real_connect(*a, **kw)))

    try:
        backup.criar_snapshot(origem, destino)
        assert False, "criar_snapshot deveria propagar a falha"
    except KeyboardInterrupt:
        pass

    assert list(destino.glob("*.db.tmp")) == []
    assert list(destino.glob("dashboard-*.db")) == []


# --- ensaio de restauracao, copia externa e retencao em camadas (bloco de producao) ---

def _origem(tmp_path):
    origem = tmp_path / "app.db"
    conn = sqlite3.connect(origem)
    conn.execute("CREATE TABLE t (x)"); conn.execute("INSERT INTO t VALUES (1)")
    conn.commit(); conn.close()
    return origem

def test_snapshot_corrompido_nao_vira_backup(tmp_path, monkeypatch):
    # o ensaio de restauracao roda ANTES do rename: parcial que nao abre e' apagado
    origem = _origem(tmp_path)
    destino = tmp_path / "backups"
    monkeypatch.setattr(backup, "verificar_snapshot",
                        lambda a: (_ for _ in ()).throw(backup.SnapshotInvalido("x")))
    with pytest.raises(backup.SnapshotInvalido):
        backup.criar_snapshot(origem, destino)
    assert list(destino.glob("*")) == []

def test_verificar_snapshot_rejeita_lixo(tmp_path):
    lixo = tmp_path / "dashboard-20260101-000000.db"
    lixo.write_bytes(b"isto nao e um banco" * 100)
    with pytest.raises(backup.SnapshotInvalido):
        backup.verificar_snapshot(lixo)

def test_copia_externa_com_checksum_conferido(tmp_path):
    origem = _origem(tmp_path)
    snap = backup.criar_snapshot(origem, tmp_path / "backups")
    fora = tmp_path / "externo"
    copia = backup.copiar_externo(snap, fora)
    assert copia.read_bytes() == snap.read_bytes()
    sha = (fora / f"{snap.name}.sha256").read_text().split()[0]
    assert sha == backup._sha256(snap)
    assert list(fora.glob("*.tmp")) == []

def test_retencao_em_camadas(tmp_path):
    # 400 dias de copias diarias -> 7 diarias + 5 semanais + 12 mensais (com sobreposicao)
    import datetime
    fora = tmp_path / "externo"; fora.mkdir()
    fim = datetime.date(2026, 9, 2)
    for i in range(400):
        d = fim - datetime.timedelta(days=i)
        (fora / f"dashboard-{d:%Y%m%d}-030000.db").write_bytes(b"x")
    backup.rotacionar_externo(fora)
    restantes = sorted(backup._data_do_nome(a) for a in fora.glob("dashboard-*.db"))
    ultimos7 = [fim - datetime.timedelta(days=i) for i in range(7)]
    assert all(d in restantes for d in ultimos7)           # diarios
    assert datetime.date(2026, 8, 31) in restantes         # ultimo dia de agosto (mensal)
    assert datetime.date(2025, 10, 31) in restantes        # 12o mes contando o atual (mensal)
    assert datetime.date(2025, 9, 30) not in restantes     # 13o mes: fora
    assert len(restantes) <= 7 + 5 + 12

def test_rodada_copia_uma_vez_por_dia_e_registra_estado(tmp_path):
    origem = _origem(tmp_path)
    fora = tmp_path / "externo"
    backup.rodada(origem, tmp_path / "backups", fora)
    assert backup.ESTADO["ultimo_snapshot"] and backup.ESTADO["ultima_copia_externa"]
    assert len(list(fora.glob("dashboard-*.db"))) == 1
    time.sleep(1.1)  # segundo snapshot com carimbo diferente, mesmo dia
    backup.rodada(origem, tmp_path / "backups", fora)
    assert len(list((tmp_path / "backups").glob("dashboard-*.db"))) == 2
    assert len(list(fora.glob("dashboard-*.db"))) == 1     # nao copiou de novo hoje

def test_rodada_registra_erro_de_acesso_a_pasta_externa(tmp_path, monkeypatch):
    # compartilhamento sem permissao: exists()/glob() levantam PermissionError antes
    # de copiar; tem que virar erro registrado, nao thread morta
    origem = _origem(tmp_path)
    monkeypatch.setattr(backup, "_copiou_hoje",
                        lambda p, h: (_ for _ in ()).throw(PermissionError("Acesso negado")))
    backup.rodada(origem, tmp_path / "backups", tmp_path / "externo")
    assert "Acesso negado" in backup.ESTADO["ultima_copia_externa_erro"]


def test_rodada_registra_erro_da_copia_sem_derrubar(tmp_path, monkeypatch):
    origem = _origem(tmp_path)
    monkeypatch.setattr(backup, "copiar_externo",
                        lambda s, p: (_ for _ in ()).throw(OSError("rede fora")))
    backup.rodada(origem, tmp_path / "backups", tmp_path / "externo")
    assert backup.ESTADO["ultimo_snapshot_erro"] is None
    assert "rede fora" in backup.ESTADO["ultima_copia_externa_erro"]


# --- arquivos ao lado do banco (issue #55): notas, espelhos, modelos e evidencias -----

def _dados_com_arquivos(tmp_path):
    """Pasta de dados como a da producao: banco + as quatro pastas, nomes pelo sha256."""
    dados = tmp_path / "dados"; dados.mkdir()
    origem = dados / "dashboard.db"
    conn = sqlite3.connect(origem)
    conn.execute("CREATE TABLE docs (caminho TEXT)")
    gravados = {}
    for pasta, ext in (("notas", "pdf"), ("espelhos", "docx"), ("modelos", "docx"), ("evidencias", "eml")):
        conteudo = f"%PDF- conteudo de {pasta}".encode()
        rel = f"{pasta}/{hashlib.sha256(conteudo).hexdigest()}.{ext}"
        (dados / pasta).mkdir()
        (dados / rel).write_bytes(conteudo)
        conn.execute("INSERT INTO docs VALUES (?)", (rel,))
        gravados[rel] = conteudo
    conn.commit(); conn.close()
    return origem, gravados


def _arquivos_no(pasta):
    return sorted(a for a in pasta.rglob("*") if a.is_file()) if pasta.exists() else []


def test_rodada_copia_as_quatro_pastas_para_o_backup(tmp_path):
    origem, gravados = _dados_com_arquivos(tmp_path)
    destino = tmp_path / "dados" / "backups"
    backup.rodada(origem, destino, None)
    for rel, conteudo in gravados.items():
        assert (destino / "arquivos" / rel).read_bytes() == conteudo, rel
    assert backup.ESTADO["ultima_copia_arquivos"] and backup.ESTADO["ultima_copia_arquivos_erro"] is None


def test_copia_ignora_temporario_em_andamento(tmp_path):
    origem, _ = _dados_com_arquivos(tmp_path)
    (tmp_path / "dados" / "notas" / "upload-123-abc.tmp").write_bytes(b"parcial")
    destino = tmp_path / "dados" / "backups"
    backup.rodada(origem, destino, None)
    assert list((destino / "arquivos" / "notas").glob("*.tmp")) == []


def test_restaurar_snapshot_devolve_banco_e_arquivos_coerentes(tmp_path):
    origem, gravados = _dados_com_arquivos(tmp_path)
    dados = tmp_path / "dados"
    destino = dados / "backups"
    backup.rodada(origem, destino, None)
    snap = sorted(destino.glob("dashboard-*.db"))[-1]

    # o pior dia: banco e pastas perdidos
    origem.unlink()
    for pasta in backup.PASTAS_ARQUIVOS:
        for a in (dados / pasta).iterdir():
            a.unlink()

    # restauracao: o snapshot volta a ser o banco e as pastas voltam do backup
    origem.write_bytes(snap.read_bytes())
    backup.copiar_arquivos(destino / "arquivos", dados)

    conn = sqlite3.connect(origem)
    citados = [r[0] for r in conn.execute("SELECT caminho FROM docs")]
    conn.close()
    assert sorted(citados) == sorted(gravados)
    for rel in citados:  # todo arquivo que o banco cita existe e e' o que foi gravado
        assert (dados / rel).read_bytes() == gravados[rel]


def test_arquivos_nao_se_multiplicam_por_snapshot(tmp_path):
    # 48 snapshots nao podem virar 48 copias dos PDFs: os nomes sao o sha256, uma copia basta
    origem, gravados = _dados_com_arquivos(tmp_path)
    destino = tmp_path / "dados" / "backups"
    backup.rodada(origem, destino, None)
    copia = destino / "arquivos" / next(iter(gravados))
    envelhecer(copia, 7200)
    antes = copia.stat().st_mtime
    time.sleep(1.1)
    backup.rodada(origem, destino, None)
    assert len(list(destino.glob("dashboard-*.db"))) == 2
    assert len(_arquivos_no(destino / "arquivos")) == len(gravados)
    assert copia.stat().st_mtime == antes  # ja' estava la': nao foi copiado de novo


def test_arquivo_que_saiu_dos_dados_continua_no_backup(tmp_path):
    # um snapshot antigo pode citar o arquivo; o backup nunca apaga o que guardou
    origem, gravados = _dados_com_arquivos(tmp_path)
    destino = tmp_path / "dados" / "backups"
    backup.rodada(origem, destino, None)
    rel = next(iter(gravados))
    (tmp_path / "dados" / rel).unlink()
    time.sleep(1.1)
    backup.rodada(origem, destino, None)
    assert (destino / "arquivos" / rel).exists()


def test_copia_externa_leva_os_arquivos(tmp_path):
    origem, gravados = _dados_com_arquivos(tmp_path)
    fora = tmp_path / "externo"
    backup.rodada(origem, tmp_path / "dados" / "backups", fora)
    for rel, conteudo in gravados.items():
        assert (fora / "arquivos" / rel).read_bytes() == conteudo, rel
    assert backup.ESTADO["ultima_copia_externa_erro"] is None


def test_copia_de_arquivo_corrompida_e_recusada(tmp_path, monkeypatch):
    # o nome e' o sha256: a copia so' conta se o que chegou ao destino bate com ele
    origem, _ = _dados_com_arquivos(tmp_path)
    destino = tmp_path / "dados" / "backups"

    def copia_truncada(a, b):
        with open(b, "wb") as f:
            f.write(b"truncado")

    monkeypatch.setattr(backup.shutil, "copyfile", copia_truncada)
    backup.rodada(origem, destino, None)
    assert "sha256" in backup.ESTADO["ultima_copia_arquivos_erro"]
    assert backup.ESTADO["ultimo_snapshot_erro"] is None  # o banco foi salvo mesmo assim
    assert _arquivos_no(destino / "arquivos") == []
