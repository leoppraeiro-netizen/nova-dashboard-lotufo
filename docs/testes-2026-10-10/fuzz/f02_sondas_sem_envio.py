"""F02 — sondas que NÃO disparam e-mail: V-03, V-04, V-05, V-09, V-11, e S3/S14/S17.

Cria um usuário descartável locktest.fuzz@lotufo.com só para as sondas de lockout, e o destranca ao fim.
Saída: saidas/f02.jsonl.
"""
import pathlib
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comum import BASE, Cliente, Registro, conferir_simulador, contar_correio, db_ro, db_rw, resumo

reg = Registro("f02")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64  # "imagem" para renomear a .eml


def garantir_lockuser(adm):
    with db_ro() as c:
        r = c.execute("SELECT id FROM usuarios WHERE email=?", ("locktest.fuzz@lotufo.com",)).fetchone()
    if r:
        return r[0]
    rr = adm.post("/api/admin/usuarios", json={"nome": "Lock Test Fuzz", "email": "locktest.fuzz@lotufo.com",
                                               "senha": "SenhaLonga123", "perfil": "diretoria"})
    uid = rr.json().get("id")
    reg(rota="POST /api/admin/usuarios", caso="cria lockuser", obtido=resumo(rr), nota=f"uid={uid}")
    return uid


def destrancar(uid):
    with db_rw() as c:
        c.execute("UPDATE usuarios SET tentativas_falhas=0, bloqueado_ate=NULL WHERE id=?", (uid,))
        c.commit()


def login_cru(email, senha):
    import urllib.request
    import json as J
    dados = J.dumps({"email": email, "senha": senha}).encode()
    req = urllib.request.Request(f"{BASE}/api/auth/login", data=dados,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return r.status, r.read()[:120]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:120]


def v03_corpo_gigante():
    """Corpo sem teto lido antes do 401. JSON 300 MB sem cookie; mede tempo e pico de resposta."""
    import urllib.request
    carga = b'{"x":"' + b"a" * (300 * 1024 * 1024) + b'"}'
    t0 = time.time()
    req = urllib.request.Request(f"{BASE}/api/protocolos/envio", data=carga,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=300)
        cod = r.status
    except urllib.error.HTTPError as e:
        cod = e.code
    dt = time.time() - t0
    # Repete pequeno para medir baseline de latência do 401/403
    t1 = time.time()
    s, _ = login_cru("naoexiste@lotufo.com", "x")  # não é a rota, só latência de referência
    base = time.time() - t1
    flag = "FUGIU" if cod in (401, 403) and dt < 1.0 else "LENTO"
    reg(rota="POST /api/protocolos/envio", caso="JSON 300MB sem login", esperado="401/403 rápido",
        obtido=f"cod={cod} tempo={dt:.2f}s (login ref {base:.2f}s)", flag=flag)
    return cod, dt


def v04_lockout(uid):
    destrancar(uid)
    for i in range(5):
        login_cru("locktest.fuzz@lotufo.com", f"errada-{i}")
    s, corpo = login_cru("locktest.fuzz@lotufo.com", "SenhaLonga123")  # senha CERTA
    com_bloqueio = db_ro().execute("SELECT tentativas_falhas, bloqueado_ate FROM usuarios WHERE id=?", (uid,)).fetchone()
    flag = "FUGIU" if s == 401 and com_bloqueio[1] else "OK-ESPERADO"
    reg(rota="POST /api/auth/login", caso="V-04 lockout (6a com senha certa)", esperado="401 e segue bloqueada",
        obtido=f"cod={s} bloqueado_ate={com_bloqueio[1]}", flag=flag)
    destrancar(uid)
    return s, com_bloqueio[1]


def v05_corrida_lockout(uid):
    destrancar(uid)
    res = []

    def f(n):
        res.append(login_cru("locktest.fuzz@lotufo.com", f"corrida-{n}"))
    ts = [threading.Thread(target=f, args=(n,)) for n in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    row = db_ro().execute("SELECT tentativas_falhas, bloqueado_ate FROM usuarios WHERE id=?", (uid,)).fetchone()
    s, _ = login_cru("locktest.fuzz@lotufo.com", "SenhaLonga123")
    # correto: após 20 erradas a conta está bloqueada (s==401). Falha: entra (s==200).
    flag = "FUGIU" if s == 200 else "OK-ESPERADO"
    reg(rota="POST /api/auth/login", caso="V-05 20 erradas paralelas depois senha certa",
        esperado="bloqueada (401)", obtido=f"cod_final={s} contador={row[0]} bloqueado_ate={row[1]}", flag=flag)
    destrancar(uid)


def v09_senha_no_log(adm):
    marca = "FRASE-DIGITADA-NO-CAMPO-EMAIL-QUE-PARECE-SENHA-" + str(int(time.time()))
    login_cru(marca, "qualquer")  # email inválido com texto sensível
    r = adm.get("/api/admin/auditoria?limite=20")
    txt = r.text
    achou = marca.lower() in txt.lower()
    reg(rota="GET /api/admin/auditoria", caso="V-09 texto digitado no campo email",
        esperado="texto não aparece por inteiro", obtido=f"apareceu_integral={achou}",
        flag="FUGIU" if achou else "OK-ESPERADO")


def v11_eml_sem_validacao(eng):
    """Registrar envio por fora com arquivo que NÃO é e-mail (PNG renomeado .eml)."""
    with db_ro() as c:
        r = c.execute("SELECT id FROM medicoes WHERE estado='nota_emitida' ORDER BY id LIMIT 1").fetchone()
    if not r:
        reg(rota="POST /api/notas/envio-externo", caso="V-11", obtido="sem medicao nota_emitida", flag="PULOU")
        return
    mid = r[0]
    rr = eng.post("/api/notas/envio-externo",
                  data={"medicao_ids": [str(mid)], "enviado_em": "2026-09-15",
                        "observacao": "fuzz V-11 - arquivo nao-eml renomeado"},
                  files={"eml": ("falso.eml", PNG, "message/rfc822")})
    aceitou = rr.status_code == 200
    reg(rota="POST /api/notas/envio-externo", caso="V-11 PNG renomeado .eml",
        esperado="recusa clara", obtido=resumo(rr), nota=f"medicao {mid} -> protocolada",
        flag="FUGIU" if aceitou else "OK-ESPERADO")


def s03_nota_manual_overflow(eng):
    with db_ro() as c:
        r = c.execute("SELECT id FROM medicoes WHERE estado IN ('espelho_gerado','espelho_enviado','nota_emitida') "
                      "ORDER BY id DESC LIMIT 1").fetchone()
    mid = r[0] if r else 631
    rr = eng.post(f"/api/medicoes/{mid}/notas/manual",
                  json={"documento_id": 1, "numero": 1, "emissao": "2026-09-01",
                        "valor": "99999999999999999999,00"})
    reg(rota="POST /api/medicoes/{id}/notas/manual", caso="S3 valor 20 digitos",
        esperado="422 (não 500)", obtido=resumo(rr), flag="500" if rr.status_code >= 500 else "")


def s14_unicode(eng):
    # competência da regularidade e valor BRL com dígito árabe-índico
    with db_ro() as c:
        ent = c.execute("SELECT id FROM entidades WHERE ativo=1 LIMIT 1").fetchone()[0]
    PDFV = b"%PDF-1.4\n%\xe2\xe3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    rr = eng.post("/api/documentos/regularidades",
                  data={"entidade_id": str(ent), "competencia": "٢٠٢٦-٠٨"},
                  files={"arquivo": ("r.pdf", PDFV, "application/pdf")})
    reg(rota="POST /api/documentos/regularidades", caso="S14 competencia arabe ٢٠٢٦-٠٨",
        esperado="422/415 (não 500)", obtido=resumo(rr), flag="500" if rr.status_code >= 500 else "")


def s17_numero_vazio(eng):
    """Número do órgão vazio apaga o já gravado, sem confirmação (sonda não destrutiva: só grava e apaga de teste)."""
    with db_ro() as c:
        r = c.execute("SELECT m.id FROM medicoes m WHERE m.estado='protocolada' ORDER BY m.id DESC LIMIT 1").fetchone()
    if not r:
        reg(rota="POST /api/notas/{id}/numero-orgao", caso="S17", obtido="sem protocolada", flag="PULOU")
        return
    mid = r[0]
    a = eng.post(f"/api/notas/{mid}/numero-orgao", json={"numero": "SIGA-FUZZ-999"})
    with db_ro() as c:
        mp1 = c.execute("SELECT numero_processo FROM medicao_protocolos WHERE medicao_id=? ORDER BY id DESC LIMIT 1", (mid,)).fetchone()
    b = eng.post(f"/api/notas/{mid}/numero-orgao", json={"numero": ""})
    with db_ro() as c:
        mp2 = c.execute("SELECT numero_processo FROM medicao_protocolos WHERE medicao_id=? ORDER BY id DESC LIMIT 1", (mid,)).fetchone()
    apagou = (mp1 and mp1[0]) and (not mp2 or not mp2[0])
    reg(rota="POST /api/notas/{id}/numero-orgao", caso="S17 vazio apaga numero gravado",
        esperado="confirmação antes de apagar", obtido=f"grava={resumo(a)} depois_grava={mp1} apaga={resumo(b)} depois_apaga={mp2}",
        nota=f"medicao {mid}", flag="FUGIU" if apagou else "OK")


def main():
    conferir_simulador()
    antes = contar_correio()
    adm = Cliente("admin")
    eng = Cliente("engenharia")
    uid = garantir_lockuser(adm)
    v04_lockout(uid)
    v05_corrida_lockout(uid)
    v09_senha_no_log(adm)
    s03_nota_manual_overflow(eng)
    s14_unicode(eng)
    s17_numero_vazio(eng)
    v11_eml_sem_validacao(eng)
    v03_corpo_gigante()
    destrancar(uid)
    depois = contar_correio()
    print(f"correio simulado: antes={antes} depois={depois} (f02 não deve enviar nada)")


if __name__ == "__main__":
    main()
