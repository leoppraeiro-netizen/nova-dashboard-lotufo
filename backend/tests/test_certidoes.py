import datetime
import pytest
from app import auditoria, auth, certidoes, db, entidades, tempo

@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@l.com", "senha-forte-123", "admin")
    yield c
    c.close()

def _reg(conn, ent=1, tipo=1, emissao="2026-08-01", validade="2026-11-01", origem="robo"):
    return certidoes.registrar(conn, 1, ent, tipo, emissao, validade,
                               f"dados/certidoes/{ent}-{tipo}-{emissao}.pdf", "a"*64, origem)

def test_vigente_e_historico(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    _reg(conn, emissao="2026-05-01", validade="2026-08-01")
    nova = _reg(conn, emissao="2026-08-01", validade="2026-11-01")
    v = certidoes.vigente(conn, 1, 1)
    assert v["id"] == nova and v["validade"] == "2026-11-01"
    antiga = certidoes.vigente(conn, 1, 1, na_data="2026-07-15")   # qual valia no protocolo X
    assert antiga["emissao"] == "2026-05-01"
    assert conn.execute("SELECT COUNT(*) c FROM certidoes").fetchone()["c"] == 2   # nada apagado

def test_vencida_e_derivada(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    _reg(conn, emissao="2026-01-01", validade="2026-02-01")
    assert certidoes.vigente(conn, 1, 1) is None
    linha = [l for l in certidoes.painel(conn) if l["entidade_id"] == 1 and l["tipo_id"] == 1][0]
    assert linha["semaforo"] == "vermelho"

def test_marcar_estado_so_revogada_ou_nao_se_aplica(conn):
    cid = _reg(conn)
    certidoes.marcar_estado(conn, 1, cid, "revogada", "órgão revogou")
    assert certidoes.vigente(conn, 1, 1) is None
    with pytest.raises(ValueError, match="inválido"):
        certidoes.marcar_estado(conn, 1, cid, "vigente", None)

def test_semaforo_ambar_ate_15_dias(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 10, 20))
    _reg(conn, emissao="2026-08-01", validade="2026-11-01")   # faltam 12 dias
    linha = [l for l in certidoes.painel(conn) if l["tipo_id"] == 1 and l["entidade_id"] == 1][0]
    assert linha["semaforo"] == "ambar"

def test_validade_antes_da_emissao_rejeita(conn):
    with pytest.raises(ValueError, match="validade"):
        _reg(conn, emissao="2026-08-01", validade="2026-07-01")


# --- alem do nucleo do brief -----------------------------------------------------

def test_semaforo_verde_e_fronteira_de_15_dias(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 10, 16))
    _reg(conn, emissao="2026-08-01", validade="2026-11-01")   # faltam 16 dias
    linha = [l for l in certidoes.painel(conn) if l["tipo_id"] == 1 and l["entidade_id"] == 1][0]
    assert linha["semaforo"] == "verde" and linha["dias"] == 16
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 10, 17))  # faltam 15
    linha = [l for l in certidoes.painel(conn) if l["tipo_id"] == 1 and l["entidade_id"] == 1][0]
    assert linha["semaforo"] == "ambar" and linha["dias"] == 15

def test_vence_hoje_ainda_e_vigente(conn, monkeypatch):
    # o orgao aceita a certidao ATE o ultimo dia de validade: `validade >= hoje`, nao `>`.
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 11, 1))
    _reg(conn, emissao="2026-08-01", validade="2026-11-01")
    v = certidoes.vigente(conn, 1, 1)
    assert v is not None
    linha = [l for l in certidoes.painel(conn) if l["tipo_id"] == 1 and l["entidade_id"] == 1][0]
    assert linha["semaforo"] == "ambar" and linha["dias"] == 0

def test_painel_cinza_para_nao_se_aplica(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    certidoes.marcar_nao_se_aplica(conn, 1, 1, 2, "empresa sem empregados no periodo")
    linha = [l for l in certidoes.painel(conn) if l["tipo_id"] == 2 and l["entidade_id"] == 1][0]
    assert linha["semaforo"] == "cinza" and linha["vigente"] is None
    # a decisao fica auditavel: QUEM decidiu e quando
    r = conn.execute("SELECT * FROM certidoes WHERE tipo_id=2").fetchone()
    assert r["estado"] == "nao_se_aplica" and r["sha256"] == "0" * 64
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE acao='certidao.nao_se_aplica'"
    ).fetchone()["c"] == 1

def test_painel_vermelho_quando_ausente(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    linhas = certidoes.painel(conn)
    assert len(linhas) == len(certidoes.tipos(conn))   # 1 entidade semeada x todos os tipos
    padrao = {t["id"] for t in certidoes.tipos(conn) if t["aplicavel_por_padrao"]}
    assert {l["semaforo"] for l in linhas if l["tipo_id"] in padrao} == {"vermelho"}
    assert {l["motivo"] for l in linhas if l["tipo_id"] not in padrao} <= {"nao_cobrada"}
    assert all(l["vigente"] is None for l in linhas)

def test_painel_ignora_entidade_desativada(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    eid = entidades.criar(conn, 1, {"nome": "Consórcio X", "cnpj": "11444777000161",
                                    "papel": "consorcio"})
    n = len(certidoes.tipos(conn))
    assert len(certidoes.painel(conn)) == 2 * n
    entidades.desativar(conn, 1, eid)
    assert len(certidoes.painel(conn)) == n

def test_renovacao_nao_apaga_a_anterior_e_auditoria_intacta(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    velha = _reg(conn, emissao="2026-05-01", validade="2026-08-01")
    nova = _reg(conn, emissao="2026-08-01", validade="2026-11-01")
    ids = [r["id"] for r in conn.execute("SELECT id FROM certidoes ORDER BY id")]
    assert ids == [velha, nova]
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE acao='certidao.registrar'").fetchone()["c"] == 2
    assert auditoria.verificar_cadeia(conn)

def test_origem_invalida_rejeita(conn):
    with pytest.raises(ValueError, match="Origem inválida"):
        _reg(conn, origem="email")

def test_sha256_invalido_rejeita(conn):
    with pytest.raises(ValueError, match="sha256"):
        certidoes.registrar(conn, 1, 1, 1, "2026-08-01", "2026-11-01", "x.pdf", "curto", "upload")

def test_data_nao_iso_rejeita(conn):
    with pytest.raises(ValueError, match="emissão"):
        _reg(conn, emissao="01/08/2026")

def test_entidade_ou_tipo_inexistente_rejeita(conn):
    with pytest.raises(ValueError, match="Entidade"):
        _reg(conn, ent=999)
    with pytest.raises(ValueError, match="Tipo de certidão"):
        _reg(conn, tipo=999)
    assert conn.execute("SELECT COUNT(*) c FROM certidoes").fetchone()["c"] == 0

def test_tipos_semeados_e_criar_tipo(conn):
    nomes = {t["nome"] for t in certidoes.tipos(conn)}
    assert {"CND Federal (RFB/PGFN)", "CRF/FGTS", "CNDT"} <= nomes
    tid = certidoes.criar_tipo(conn, 1, "CND Estadual MT", "estadual", "SEFAZ-MT", False)
    novo = [t for t in certidoes.tipos(conn) if t["id"] == tid][0]
    assert novo["jurisdicao"] == "estadual" and novo["aplicavel_por_padrao"] == 0
    with pytest.raises(ValueError, match="já existe"):
        certidoes.criar_tipo(conn, 1, "CND Estadual MT", "estadual", "SEFAZ-MT", True)
    with pytest.raises(ValueError, match="Jurisdição inválida"):
        certidoes.criar_tipo(conn, 1, "ISS", "distrital", "Prefeitura", True)

def test_marcar_estado_preserva_observacao_e_audita(conn, monkeypatch):
    """Marcar SEM observacao nova nao apaga a anterior (COALESCE).

    O segundo `marcar_estado` na mesma certidao passou a ser recusado no gate 2 (so
    se transita a partir de 'vigente'), entao a preservacao e' exercitada com duas
    certidoes: uma marcada com motivo e outra sem.
    """
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    com_motivo = _reg(conn)
    sem_motivo = _reg(conn, emissao="2026-08-02")
    certidoes.marcar_estado(conn, 1, com_motivo, "revogada", "ofício 12/2026")
    certidoes.marcar_estado(conn, 1, sem_motivo, "revogada", None)
    linhas = {r["id"]: r for r in conn.execute("SELECT * FROM certidoes")}
    assert linhas[com_motivo]["observacao"] == "ofício 12/2026"
    assert linhas[sem_motivo]["observacao"] is None
    assert auditoria.verificar_cadeia(conn)

def test_marcar_estado_de_certidao_inexistente(conn):
    with pytest.raises(ValueError, match="não encontrada"):
        certidoes.marcar_estado(conn, 1, 999, "revogada", None)

def test_mutacao_falha_nao_deixa_rastro(conn):
    with pytest.raises(ValueError):
        _reg(conn, ent=999)
    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"] == 0


# --- gate 2: correcoes do revisor externo ----------------------------------------

def test_revogar_hoje_nao_apaga_o_passado(conn, monkeypatch):
    """Item 1 do gate 2. Revogacao vale A PARTIR do dia em que foi registrada.

    Antes do conserto, `estado='revogada'` sumia com a certidao em TODA data --
    inclusive em julho, quando ela valia e foi protocolada. O orgao pergunta "o que
    valia no dia X"; responder "nada" porque o orgao cassou o documento em setembro
    e' apagar a prova de um protocolo legitimo.
    """
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    cid = _reg(conn, emissao="2026-05-01", validade="2026-11-01")
    certidoes.marcar_estado(conn, 1, cid, "revogada", "órgão cassou em setembro")

    valia_em_julho = certidoes.vigente(conn, 1, 1, na_data="2026-07-15")
    assert valia_em_julho is not None and valia_em_julho["id"] == cid
    assert certidoes.vigente(conn, 1, 1) is None          # hoje, nao vale mais
    # a data da decisao fica gravada, nao inferida
    assert conn.execute("SELECT estado_em FROM certidoes WHERE id=?",
                        (cid,)).fetchone()["estado_em"] == "2026-09-01"


def test_revogacao_nao_vale_no_proprio_dia_nem_depois(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    cid = _reg(conn, emissao="2026-05-01", validade="2026-11-01")
    certidoes.marcar_estado(conn, 1, cid, "revogada", None)
    assert certidoes.vigente(conn, 1, 1, na_data="2026-08-31") is not None
    assert certidoes.vigente(conn, 1, 1, na_data="2026-09-01") is None
    assert certidoes.vigente(conn, 1, 1, na_data="2026-10-01") is None


def test_marcar_nao_se_aplica_hoje_nao_apaga_o_passado(conn, monkeypatch):
    """I1 da revisao final: o espelho do item 1 do gate 2 para o OUTRO estado marcavel.

    Marcar 'nao_se_aplica' pela rota de estado age numa certidao que EXISTE, com PDF e
    datas reais. Com so' 'revogada' no filtro de `vigente`, essa marcacao sumia com a
    certidao em TODA data -- inclusive em julho, quando ela valia e foi protocolada."""
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    cid = _reg(conn, emissao="2026-05-01", validade="2026-11-01")
    certidoes.marcar_estado(conn, 1, cid, "nao_se_aplica", "não é contribuinte")

    valia_em_julho = certidoes.vigente(conn, 1, 1, na_data="2026-07-15")
    assert valia_em_julho is not None and valia_em_julho["id"] == cid
    assert certidoes.vigente(conn, 1, 1, na_data="2026-08-31") is not None
    assert certidoes.vigente(conn, 1, 1) is None          # hoje, nao vale mais
    assert certidoes.vigente(conn, 1, 1, na_data="2026-10-01") is None


def test_nao_se_aplica_tambem_grava_estado_em(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    cid = certidoes.marcar_nao_se_aplica(conn, 1, 1, 2, "sem empregados")
    assert conn.execute("SELECT estado_em FROM certidoes WHERE id=?",
                        (cid,)).fetchone()["estado_em"] == "2026-09-01"


def test_nao_se_aplica_recusa_par_com_certidao_vigente(conn, monkeypatch):
    """Achado 4 do gate 3. "Não se aplica" e "aqui está a certidão" sao afirmacoes
    contrarias sobre o mesmo par, e a declaracao e' sempre a decisao MAIS RECENTE:
    passava por cima de uma certidao valida arquivada e apagava a cobranca dela."""
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    _reg(conn, emissao="2026-08-01", validade="2026-11-01")
    with pytest.raises(ValueError, match="01/11/2026"):
        certidoes.marcar_nao_se_aplica(conn, 1, 1, 1, "sem inscrição")
    assert conn.execute("SELECT COUNT(*) c FROM certidoes").fetchone()["c"] == 1
    assert not conn.in_transaction
    # depois de vencer, a declaracao volta a ser legitima
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 11, 2))
    assert certidoes.marcar_nao_se_aplica(conn, 1, 1, 1, "sem inscrição")


def test_marcar_estado_so_transita_a_partir_de_vigente(conn, monkeypatch):
    """Item 2 do gate 2. Revogar duas vezes gravava DUAS linhas de auditoria para
    uma decisao que aconteceu uma vez, e 'nao_se_aplica' em cima de 'revogada'
    reescrevia o passado sem que ninguem visse."""
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    cid = _reg(conn)
    certidoes.marcar_estado(conn, 1, cid, "revogada", "ofício 12/2026")
    with pytest.raises(ValueError, match="já está revogada"):
        certidoes.marcar_estado(conn, 1, cid, "revogada", None)
    with pytest.raises(ValueError, match="já está revogada"):
        certidoes.marcar_estado(conn, 1, cid, "nao_se_aplica", None)
    # nada mudou e a auditoria tem UMA linha so
    r = conn.execute("SELECT * FROM certidoes WHERE id=?", (cid,)).fetchone()
    assert r["estado"] == "revogada" and r["observacao"] == "ofício 12/2026"
    assert conn.execute("SELECT COUNT(*) c FROM audit_log "
                        "WHERE acao='certidao.marcar_estado'").fetchone()["c"] == 1
    assert auditoria.verificar_cadeia(conn)


def test_nsa_antigo_nao_ressuscita_quando_a_certidao_vence(conn, monkeypatch):
    """Item 3 do gate 2. NSA em janeiro + certidao em marco + vencimento em abril
    tem que dar VERMELHO -- a entidade voltou a ter a obrigacao e esta sem certidao.
    Antes, qualquer linha 'nao_se_aplica' historica pintava cinza para sempre e o
    painel escondia uma pendencia real."""
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 1, 10))
    certidoes.marcar_nao_se_aplica(conn, 1, 1, 1, "sem obrigação no período")

    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 3, 1))
    _reg(conn, emissao="2026-03-01", validade="2026-04-01")
    linha = [l for l in certidoes.painel(conn) if l["entidade_id"] == 1
             and l["tipo_id"] == 1][0]
    assert linha["semaforo"] == "verde"

    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 4, 15))
    linha = [l for l in certidoes.painel(conn) if l["entidade_id"] == 1
             and l["tipo_id"] == 1][0]
    assert linha["semaforo"] == "vermelho", "NSA antigo nao pode voltar a valer"


def test_certidao_anexada_depois_do_nsa_manda_mesmo_com_emissao_anterior(conn, monkeypatch):
    """I2 da revisao final. `ORDER BY emissao DESC` respondia "qual documento cobre a
    data", nao "qual foi a ultima DECISAO": a certidao antiga que a mesa achou na pasta
    e anexou DEPOIS do NSA perdia para ele, e no dia em que ela vencia o par voltava a
    CINZA -- escondendo a pendencia que a propria mesa acabara de reconhecer."""
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 1, 10))
    certidoes.marcar_nao_se_aplica(conn, 1, 1, 1, "sem obrigação no período")

    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 1, 20))
    _reg(conn, emissao="2026-01-05", validade="2026-02-01")   # emissao ANTERIOR ao NSA
    assert certidoes.nao_se_aplica_vigora(conn, 1, 1) is False

    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 2, 15))
    assert certidoes.nao_se_aplica_vigora(conn, 1, 1) is False
    linha = [l for l in certidoes.painel(conn) if l["entidade_id"] == 1
             and l["tipo_id"] == 1][0]
    assert linha["semaforo"] == "vermelho", "NSA anterior a certidao nao pode voltar a valer"


def test_nsa_recente_continua_cinza(conn, monkeypatch):
    """A correcao do item 3 nao pode quebrar o caso legitimo: NSA depois da ultima
    certidao continua sendo a palavra final."""
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 3, 1))
    _reg(conn, emissao="2026-01-01", validade="2026-02-01")
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 3, 2))
    certidoes.marcar_nao_se_aplica(conn, 1, 1, 1, "deixou de ser contribuinte")
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 4, 15))
    linha = [l for l in certidoes.painel(conn) if l["entidade_id"] == 1
             and l["tipo_id"] == 1][0]
    assert linha["semaforo"] == "cinza"


def test_vigente_recusa_data_malformada(conn):
    """Item 4 do gate 2. `na_data` ia direto para uma comparacao de STRING: "2026-9-1"
    e "lixo" comparavam lexicograficamente e devolviam resposta com cara de certa."""
    for ruim in ("2026-9-1", "lixo", "01/07/2026", ""):
        with pytest.raises(ValueError, match="inválida"):
            certidoes.vigente(conn, 1, 1, na_data=ruim)


def test_painel_cinza_para_tipo_nao_cobrado_por_padrao(conn, monkeypatch):
    """Achado 1 do passe visual. `checklist.py` e `paineis.py` so' cobram tipos
    `aplicavel_por_padrao`; a matriz pintava vermelho o mesmo par e a tela dizia
    "pendente" enquanto o checklist do contrato dizia "pronto"."""
    tid = certidoes.criar_tipo(conn, 1, "CND Estadual MT", "estadual", "SEFAZ-MT", False)
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    def linha():
        return [l for l in certidoes.painel(conn) if l["entidade_id"] == 1
                and l["tipo_id"] == tid][0]
    assert linha()["semaforo"] == "cinza" and linha()["motivo"] == "nao_cobrada"

    # com certidao VALENDO, comporta-se como qualquer outra: o que vale hoje e' fato
    cid = _reg(conn, tipo=tid, emissao="2026-08-01", validade="2026-12-01")
    assert linha()["semaforo"] == "verde" and linha()["motivo"] is None

    # depois de vencer, VOLTA a cinza/nao_cobrada (R15): o historico do par nao
    # transforma tipo de excecao em exigencia -- so' o cadastro do tipo faz isso
    # (regra 3 do checklist). A emissao vencida vai junto, como informacao.
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2027, 1, 5))
    assert linha()["semaforo"] == "cinza" and linha()["motivo"] == "nao_cobrada"
    assert linha()["vigente"] is None and linha()["ultima"]["id"] == cid


def test_painel_devolve_a_ultima_emissao_vencida(conn, monkeypatch):
    """Achado 4: "venceu em 13/08" e "nunca foi cadastrada" pintam igual, mas sao
    problemas diferentes para quem opera (renovar x emitir pela primeira vez)."""
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    cid = _reg(conn, emissao="2026-05-01", validade="2026-08-13")
    linha = [l for l in certidoes.painel(conn) if l["entidade_id"] == 1
             and l["tipo_id"] == 1][0]
    assert linha["semaforo"] == "vermelho" and linha["vigente"] is None
    assert linha["ultima"]["id"] == cid and linha["ultima"]["validade"] == "2026-08-13"
    # par que nunca teve emissao continua sem nada a mostrar
    nunca = [l for l in certidoes.painel(conn) if l["entidade_id"] == 1
             and l["tipo_id"] == 2][0]
    assert nunca["ultima"] is None


def test_vigente_e_a_de_maior_validade_mesmo_anexada_antes(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    nova = _reg(conn, emissao="2026-08-20", validade="2026-12-01")
    _reg(conn, emissao="2026-08-25", validade="2026-09-20")      # emissao mais nova, validade menor
    assert certidoes.vigente(conn, 1, 1)["id"] == nova
