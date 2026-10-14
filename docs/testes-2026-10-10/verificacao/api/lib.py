"""Ajudantes da verificacao A (porta 8081). Senhas lidas do arquivo de usuarios de teste."""
import glob
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import httpx2 as httpx  # o venv expoe o httpx como pacote httpx2
sys.stdout.reconfigure(encoding="utf-8")  # -I ignora PYTHONIOENCODING

BASE = "http://127.0.0.1:8081"
RAIZ = Path(r"C:\Users\<usuario>\Nova Dashboard Lotufo\backend\dados\verif")
DB = RAIZ / "dashboard.db"
ENVIADOS = RAIZ / "correio-simulado" / "enviados"
USUARIOS = Path(r"C:\Users\<usuario>\Nova Dashboard Lotufo\backend\dados\usuarios-teste.txt")


def credenciais(perfil: str) -> tuple[str, str]:
    for linha in USUARIOS.read_text(encoding="utf-8").splitlines():
        partes = linha.split("\t")
        if len(partes) >= 3 and partes[2].strip() == perfil:
            return partes[0].strip(), partes[1].strip()
    raise SystemExit(f"perfil {perfil} nao achado")


class Sessao:
    def __init__(self, perfil: str = "engenharia", timeout: float = 60):
        self.cli = httpx.Client(base_url=BASE, timeout=timeout)
        email, senha = credenciais(perfil)
        r = self.cli.post("/api/auth/login", json={"email": email, "senha": senha})
        if r.status_code != 200:
            raise SystemExit(f"login {perfil} falhou: {r.status_code} {r.text[:200]}")
        self.csrf = r.json()["csrf"]
        self.cli.headers["X-CSRF-Token"] = self.csrf
        self.perfil = perfil

    def get(self, url, **kw):
        return self.cli.get(url, **kw)

    def post(self, url, **kw):
        return self.cli.post(url, **kw)

    def put(self, url, **kw):
        return self.cli.put(url, **kw)


def enviados() -> list[str]:
    ENVIADOS.mkdir(parents=True, exist_ok=True)
    return sorted(glob.glob(str(ENVIADOS / "*.json")))


def n_enviados() -> int:
    return len(enviados())


def ler_enviado(caminho: str) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def sql(consulta: str, *args):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(consulta, args).fetchall()]
    finally:
        conn.close()


def resumo(r: httpx.Response, n: int = 300) -> str:
    return f"{r.status_code} {r.text[:n]}"


def titulo(t: str):
    print("\n" + "=" * 8, t, "=" * 8)
