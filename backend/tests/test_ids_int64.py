"""Testes de quebra 10/10/2026, A-07: id acima de 2^63-1 em qualquer rota.

O sqlite3 levanta OverflowError ao receber inteiro maior que int64 -> 500 em 31 rotas. Todo id inteiro de
caminho e de consulta tem de ser recusado na entrada (422), antes de chegar ao banco.
"""
import re

GRANDE = "9223372036854775808"  # 2^63


def _chamar(client, metodo, url):
    try:
        return client.request(metodo, url, json={})
    except Exception as e:  # TestClient relanca o erro do servidor: e' o 500
        return type("R", (), {"status_code": 500, "text": repr(e), "json": lambda self: {}})()


def _locais(r) -> list[list]:
    detalhe = r.json().get("detail") if r.status_code == 422 else None
    return [e.get("loc") for e in detalhe] if isinstance(detalhe, list) else []


def test_id_acima_de_int64_nunca_da_500(client_admin):
    paths = client_admin.app.openapi()["paths"]
    falhas, vistos = [], 0
    for caminho, ops in paths.items():
        for metodo, op in ops.items():
            params = [p for p in op.get("parameters", []) if p["in"] in ("path", "query")]
            inteiros = [p for p in params if "integer" in str(p["schema"])]
            if not any(p["in"] == "path" for p in params) and not inteiros:
                continue
            vistos += 1
            url = re.sub(r"\{[^}]+\}", GRANDE, caminho)
            consulta = [f"{p['name']}={GRANDE}" for p in inteiros if p["in"] == "query"]
            if consulta:
                url += "?" + "&".join(consulta)
            r = _chamar(client_admin, metodo.upper(), url)
            if r.status_code not in (404, 405, 422):
                falhas.append(f"{metodo.upper()} {url} -> {r.status_code} {r.text[:120]}")
                continue
            for p in inteiros:  # o id inteiro e' recusado pela validacao da entrada, nao por acaso
                if [p["in"], p["name"]] not in _locais(r):
                    falhas.append(f"{metodo.upper()} {url} -> {p['in']} {p['name']} sem teto ({r.status_code})")
    assert vistos > 60
    assert falhas == [], "\n".join(falhas)
