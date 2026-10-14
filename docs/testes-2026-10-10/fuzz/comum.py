"""Utilitários comuns do fuzz de API (fase 1, testes de quebra 10/10/2026).

- Alvo FIXO: http://127.0.0.1:8080 (dev). Qualquer outra base é recusada.
- Credenciais lidas em tempo de execução de backend/dados/usuarios-teste.txt (nunca impressas).
- `conferir_simulador()` sobe pelos processos da porta 8080 e exige DASH_GRAPH_SIMULADOR e DASH_SEM_JOBS.
"""
import json
import pathlib
import sqlite3
import subprocess

import requests

BASE = "http://127.0.0.1:8080"
RAIZ = pathlib.Path(__file__).resolve().parents[3]
DADOS = RAIZ / "backend" / "dados"
DB = DADOS / "dashboard.db"
CORREIO = DADOS / "correio-simulado" / "enviados"
CREDS = DADOS / "usuarios-teste.txt"
SAIDA = pathlib.Path(__file__).with_name("saidas")
SAIDA.mkdir(exist_ok=True)

assert BASE.startswith("http://127.0.0.1:8080"), "alvo único é a 8080 de dev"
assert "DashboardLotufo" not in str(DB).replace("Nova Dashboard Lotufo", ""), "nunca a produção"


def credenciais() -> dict:
    """perfil -> (email, senha). Só contas de teste: @lotufo.com, ou as antigas do domínio de teste .dev."""
    out = {}
    for linha in CREDS.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.startswith("#"):
            continue
        partes = linha.split("\t")
        email, senha, perfil = partes[0], partes[1], partes[2]
        dominio = email.rsplit("@", 1)[-1].lower().split(".")
        assert len(dominio) == 2 and dominio[0] == "lotufo" and dominio[1] in ("com", "dev"), "só contas de teste"
        out[perfil] = (email, senha)
    return out


class Cliente:
    """Sessão logada (ou anônima) com o CSRF da sessão."""

    def __init__(self, perfil: str | None = None):
        self.s = requests.Session()
        self.csrf = None
        self.perfil = perfil
        if perfil:
            email, senha = credenciais()[perfil]
            r = self.s.post(f"{BASE}/api/auth/login", json={"email": email, "senha": senha}, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"login {perfil} falhou: {r.status_code} {r.text[:200]}")
            self.csrf = self.s.get(f"{BASE}/api/auth/eu", timeout=30).json()["csrf"]

    def req(self, metodo, caminho, csrf=True, timeout=120, **kw):
        assert caminho.startswith("/"), caminho
        h = dict(kw.pop("headers", {}) or {})
        if csrf and self.csrf:
            h["X-CSRF-Token"] = self.csrf
        return self.s.request(metodo, BASE + caminho, headers=h, timeout=timeout, **kw)

    def get(self, c, **kw):
        return self.req("GET", c, **kw)

    def post(self, c, **kw):
        return self.req("POST", c, **kw)

    def put(self, c, **kw):
        return self.req("PUT", c, **kw)


def conferir_simulador() -> str:
    """Exige que o processo da 8080 tenha subido com o simulador de e-mail e sem jobs."""
    ps = r"""
$p=(Get-NetTCPConnection -LocalPort 8080 -State Listen).OwningProcess | Select-Object -First 1
$cur=$p; $out=@()
for($i=0;$i -lt 6;$i++){ $w=Get-CimInstance Win32_Process -Filter "ProcessId=$cur"; if(-not $w){break}; $out+="[$cur] $($w.CommandLine)"; $cur=$w.ParentProcessId }
$out -join "`n"
"""
    txt = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    if "DASH_GRAPH_SIMULADOR='dados/correio-simulado'" not in txt or "DASH_SEM_JOBS='1'" not in txt:
        raise SystemExit("PARE: processo da 8080 sem DASH_GRAPH_SIMULADOR/DASH_SEM_JOBS\n" + txt)
    return txt


def contar_correio() -> int:
    return len(list(CORREIO.glob("*.json"))) if CORREIO.exists() else 0


def db_ro():
    c = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def db_rw():
    """Só para destrancar conta de teste e preparar cenário (anotado no relatório)."""
    return sqlite3.connect(DB.as_posix(), timeout=10)


def resumo(r, n=200):
    try:
        corpo = json.dumps(r.json(), ensure_ascii=False)[:n]
    except Exception:
        corpo = r.text[:n]
    return f"{r.status_code} {corpo}"


class Registro:
    """Junta resultados em JSONL para o relatório."""

    def __init__(self, nome):
        self.arq = SAIDA / f"{nome}.jsonl"
        self.arq.write_text("", encoding="utf-8")

    def __call__(self, **kw):
        with self.arq.open("a", encoding="utf-8") as f:
            f.write(json.dumps(kw, ensure_ascii=False, default=str) + "\n")
        flag = kw.get("flag", "")
        if flag:
            print(f"[{flag}] {kw.get('rota')} {kw.get('caso','')} -> {kw.get('obtido')}")
