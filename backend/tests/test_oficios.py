"""Numero do oficio (spec §5.4): digitado, canonico, com aviso de repetido."""
import pytest

from app import auth, db, oficios


def test_canonico_aceita_as_formas_digitadas():
    for digitado in ("301", "CT 301", "CT-301-LT-2026", "CT/301/LT/2026", "ct nº 301"):
        assert oficios.canonico(digitado, "LT", 2026) == "CT-301-LT-2026"
    assert oficios.canonico("68", "LT", 2026) == "CT-068-LT-2026"
    assert oficios.canonico("CT/122/LT/2025", "LT", 2026) == "CT-122-LT-2025"   # ano digitado manda
    assert oficios.canonico("48", None, 2026) == "CARTA-048-2026"
    with pytest.raises(ValueError):
        oficios.canonico("sem numero", "LT", 2026)


def test_na_carta():
    assert oficios.na_carta("CT-301-LT-2026") == "CT/301/LT/2026"
    assert oficios.na_carta("CARTA-048-2026") == "CARTA Nº 048/2026"


def test_usos_acha_protocolo_com_o_mesmo_numero(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    uid = auth.criar_usuario(c, "U", "u@l.com", "senha-forte-123", "admin")
    c.execute("INSERT INTO contratos (id, orgao, numero_instrumento, objeto, valor_original_centavos, nome_curto) "
              "VALUES (1,'SINFRA','IC 1/2026','Obra',100,'Obra')")
    c.execute("INSERT INTO protocolos (contrato_id, etapa, natureza, numero_oficio, usuario_id) "
              "VALUES (1,'unico','execucao','CT-301-LT-2026',?)", (uid,))
    c.commit()
    assert oficios.usos(c, "CT-301-LT-2026") and not oficios.usos(c, "CT-302-LT-2026")
    assert oficios.usos(c, "CT-301-LT-2026", ignorar=("protocolo", 1)) == []
    c.execute("INSERT INTO pleitos (contrato_id, tipo, numero_oficio) VALUES (1, 'prazo', 'CT-302-LT-2026')")
    c.commit()
    assert oficios.usos(c, "CT-302-LT-2026") == ["pleito de prazo 1 (Obra)"]
    c.close()
