"""Grava a linha de base (maior id por tabela) do banco de DEV e mostra ids úteis.

Só leitura (abre o SQLite em mode=ro). Uso:
  backend/.venv/Scripts/python.exe -I docs/testes-2026-10-10/fuzz/linha_base.py [--gravar]
"""
import json
import pathlib
import sqlite3
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[3]
DB = RAIZ / "backend" / "dados" / "dashboard.db"
SAIDA = pathlib.Path(__file__).with_name("linha_base_ids.json")


def main():
    c = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    base = {}
    for (n,) in c.execute("select name from sqlite_master where type='table'"):
        cols = [r[1] for r in c.execute(f"pragma table_info({n})")]
        if "id" in cols:
            base[n] = c.execute(f"select coalesce(max(id),0) from {n}").fetchone()[0]
    if "--gravar" in sys.argv:
        SAIDA.write_text(json.dumps(base, indent=1), encoding="utf-8")
        print("gravado", SAIDA)
    print(base)
    print("contratos:")
    for r in c.execute(
        "select c.id, c.nome_curto, c.estado, o.chave, o.familia, c.entidade_id,"
        " (select situacao from espelho_regras r where r.contrato_id=c.id)"
        " from contratos c left join orgaos o on o.id=c.orgao_id"
    ):
        print(" ", r)
    print("medicoes por estado:", list(c.execute("select estado,count(*) from medicoes group by estado")))
    print("protocolos:", list(c.execute("select id,contrato_id,etapa,natureza,situacao,numero_oficio from protocolos")))
    print("espelhos:", list(c.execute("select id,contrato_id,numero,competencia,versao,situacao,envio_id from espelhos")))
    print("pleitos:", list(c.execute("select situacao,count(*) from pleitos group by situacao")))
    print("usuarios teste:", list(c.execute("select id,email,perfil,ativo,tentativas_falhas,bloqueado_ate from usuarios where id>=5")))


if __name__ == "__main__":
    main()
