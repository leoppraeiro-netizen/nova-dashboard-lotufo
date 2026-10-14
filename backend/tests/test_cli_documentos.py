"""`python -m app.cli documentos importar <pasta>`: carga das certidoes vigentes (bloco 4)."""
import datetime
import pathlib

from app import auth, cli, db, leitura_pdf, tempo
from tests.conftest import _pdf_com_texto

FIX = pathlib.Path(__file__).parent / "fixtures" / "certidoes"


def test_importar_ensaio_e_real(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 23))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@l.com", "senha-forte-123", "admin"); c.close()
    pasta = tmp_path / "Certidoes" / "Lotufo"
    pasta.mkdir(parents=True)
    textos = {"cndt.pdf": "trabalhista-alfa", "fgts.pdf": "fgts-alfa", "vazio.pdf": None}
    for nome in textos:
        (pasta / nome).write_bytes(_pdf_com_texto(nome))
    por_pdf = {_pdf_com_texto(n): (FIX / f"{t}.txt").read_text(encoding="utf-8") if t else ""
               for n, t in textos.items()}
    monkeypatch.setattr(leitura_pdf, "texto_de_pdf_com_limite", lambda pdf: por_pdf[pdf])
    args = ["documentos", "importar", str(tmp_path / "Certidoes"), "--usuario", "u@l.com"]
    assert cli.main(args + ["--ensaio"]) == 0
    saida = capsys.readouterr().out
    assert "ENSAIO" in saida and "gravadas: 1" in saida and "vencidas: 1" in saida and "sem_leitura: 1" in saida
    c = db.get_conn()
    assert c.execute("SELECT COUNT(*) FROM certidoes").fetchone()[0] == 0
    c.close()
    assert cli.main(args) == 0
    c = db.get_conn()
    assert c.execute("SELECT COUNT(*) FROM certidoes").fetchone()[0] == 1       # a CNDT (o FGTS de 09/08 venceu)
    c.close()
