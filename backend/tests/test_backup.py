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


# --- saude do backup na tela de Administracao (issue #31) ----------------------

def _agora():
    import datetime
    return datetime.datetime(2026, 10, 13, 12, 0, tzinfo=datetime.timezone.utc)

def _snapshot_com_idade(pasta, nome, segundos, tamanho=10):
    pasta.mkdir(exist_ok=True)
    arq = pasta / nome
    arq.write_bytes(b"x" * tamanho)
    instante = _agora().timestamp() - segundos
    os.utime(arq, (instante, instante))
    return arq

def test_situacao_conta_guardados_e_le_o_ultimo_do_disco(tmp_path):
    # o ultimo backup vem do disco, nao da memoria: sobrevive ao servidor reiniciar
    local = tmp_path / "backups"
    _snapshot_com_idade(local, "dashboard-20261013-060000.db", 3 * 3600, tamanho=5)
    _snapshot_com_idade(local, "dashboard-20261013-070000.db", 1800, tamanho=2048)
    # nome que ordena depois mas foi gravado antes: o ultimo e' o mais recente pelo disco, nao pelo nome
    _snapshot_com_idade(local, "dashboard-20261013-090000.db", 4 * 3600, tamanho=7)
    (local / "dashboard-20261013-080000-pid9.db.tmp").write_bytes(b"parcial")  # nao conta
    s = backup.situacao(local, True, _agora())
    assert s["guardados"] == 3 and s["copia_externa_configurada"] is True
    assert s["tamanho_bytes"] == 2048
    assert s["ultimo_backup"] == "2026-10-13T07:30:00-04:00"  # hora de Cuiaba
    assert s["atrasado"] is False

def test_situacao_atrasado_acima_de_2h(tmp_path):
    local = tmp_path / "backups"
    arq = _snapshot_com_idade(local, "dashboard-20261013-060000.db", 2 * 3600 - 60)
    assert backup.situacao(local, False, _agora())["atrasado"] is False
    instante = _agora().timestamp() - (2 * 3600 + 60)
    os.utime(arq, (instante, instante))
    s = backup.situacao(local, False, _agora())
    assert s["atrasado"] is True and s["copia_externa_configurada"] is False

def test_situacao_sem_backup_e_atrasado(tmp_path):
    s = backup.situacao(tmp_path / "nao-existe", False, _agora())
    assert s["guardados"] == 0 and s["ultimo_backup"] is None and s["tamanho_bytes"] is None
    assert s["atrasado"] is True

def test_situacao_pasta_ilegivel_nao_derruba_e_fica_atrasado(tmp_path, monkeypatch):
    local = tmp_path / "backups"
    _snapshot_com_idade(local, "dashboard-20261013-070000.db", 1800)
    def negado(self, padrao):
        raise PermissionError("Acesso negado")
    monkeypatch.setattr(type(local), "glob", negado)
    s = backup.situacao(local, False, _agora())
    assert s["guardados"] == 0 and s["atrasado"] is True

def test_situacao_traz_o_ultimo_erro(tmp_path, monkeypatch):
    monkeypatch.setitem(backup.ESTADO, "ultimo_snapshot_erro", "2026-10-13T08:00:00-04:00: disco cheio")
    s = backup.situacao(tmp_path / "backups", False, _agora())
    assert s["ultimo_snapshot_erro"].endswith("disco cheio")
    assert "ultima_copia_externa_erro" in s
