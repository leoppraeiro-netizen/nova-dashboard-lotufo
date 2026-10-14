"""F01 — matriz de permissões (anônimo/diretoria/engenharia/sem CSRF) e ids hostis em TODAS as rotas do openapi.

Seguro por construção:
- matriz: corpo vazio + id inexistente (999999); a recusa esperada (401/403) vem antes de qualquer efeito;
- ids hostis: só em rotas com id no caminho, sempre com ids que não existem (0, -1, 2^63-1, 2^63, 10^20, texto),
  com corpo mínimo VÁLIDO para chegar ao handler; destinatários só @exemplo.com.
Saída: saidas/f01.jsonl; imprime só o que fugiu do esperado.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comum import SAIDA, Cliente, Registro, conferir_simulador, contar_correio, resumo

SEM_LOGIN = {"/api/health", "/api/auth/login", "/api/auth/logout"}
ADMIN = ("/api/admin/", "/api/rm/sincronizar", "/api/rm/reconciliacao")
CORREIO_GET = "/api/correio/"  # editar_cadastros também nos GET


def precisa(metodo, caminho):
    """Permissão esperada pelo oráculo (inventário §3)."""
    if caminho in SEM_LOGIN:
        return None
    if caminho.startswith(ADMIN):
        return "administrar"
    if metodo != "GET" or caminho.startswith(CORREIO_GET) or caminho.endswith("/envio") and "/espelhos/" in caminho:
        return "editar_cadastros"
    return "ver_paineis"


def resolver(schema, comps):
    if "$ref" in schema:
        return comps[schema["$ref"].split("/")[-1]]
    return schema


def exemplo(schema, comps, nome=""):
    s = resolver(schema, comps)
    if "anyOf" in s:
        opcoes = [o for o in s["anyOf"] if o.get("type") != "null"]
        return exemplo(opcoes[0], comps, nome) if opcoes else None
    if "enum" in s:
        return s["enum"][0]
    if "const" in s:
        return s["const"]
    t = s.get("type")
    if t == "object" or "properties" in s:
        req = s.get("required", [])
        return {k: exemplo(v, comps, k) for k, v in s.get("properties", {}).items() if k in req}
    if t == "array":
        item = exemplo(s.get("items", {}), comps, nome)
        n = max(1, s.get("minItems", 1))
        if nome in ("para", "copia", "cco"):
            return ["fuzz@exemplo.com"]
        return [item] * n
    if t == "integer":
        return max(1, s.get("minimum", 1))
    if t == "number":
        return 1
    if t == "boolean":
        return False
    if t == "string":
        if s.get("format") == "binary":
            return "__arquivo__"
        if s.get("format") == "date":
            return "2026-09-15"
        pat = s.get("pattern", "")
        if "-" in pat and "4" in pat and "12" in pat or nome in ("competencia", "data_base_mes"):
            return "2026-09"
        if nome in ("valor",):
            return "1,00"
        if nome in ("numero_oficio",):
            return "CT-999-LT-2026"
        if nome in ("url",):
            return "https://exemplo.com/fuzz-arquivo"
        if nome in ("assunto", "motivo", "justificativa", "corpo", "nome", "observacao"):
            return "fuzz de teste - pode ignorar"
        if nome == "enviado_em":
            return "2026-09-15"
        return "x" * max(1, s.get("minLength", 1))
    return "x"


PDF_MIN = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def montar_corpo(op, comps):
    rb = op.get("requestBody", {}).get("content", {})
    if "application/json" in rb:
        return {"json": exemplo(rb["application/json"]["schema"], comps)}
    if "multipart/form-data" in rb:
        dados = exemplo(rb["multipart/form-data"]["schema"], comps)
        files, data = {}, {}
        for k, v in dados.items():
            if v == "__arquivo__":
                files[k] = ("fuzz.pdf", PDF_MIN, "application/pdf")
            elif isinstance(v, list):
                data[k] = [str(x) for x in v]
            else:
                data[k] = str(v)
        return {"files": files or None, "data": data}
    return {}


def preencher(caminho, valor):
    return re.sub(r"\{[^}]+\}", str(valor), caminho)


def main():
    conferir_simulador()
    antes = contar_correio()
    spec = json.loads((SAIDA / "openapi.json").read_text(encoding="utf-8"))
    comps = spec["components"]["schemas"]
    reg = Registro("f01")
    anon, dir_, eng, adm = Cliente(), Cliente("diretoria"), Cliente("engenharia"), Cliente("admin")

    # ---- matriz de permissão ----
    for caminho, ops in spec["paths"].items():
        for metodo, op in ops.items():
            M = metodo.upper()
            if caminho == "/api/auth/logout":
                continue
            p = preencher(caminho, 999999)
            perm = precisa(M, caminho)
            if perm is None:
                continue
            # anônimo
            r = anon.req(M, p, csrf=False)
            reg(rota=f"{M} {caminho}", caso="anonimo", esperado=401, obtido=resumo(r),
                flag="" if r.status_code == 401 else "FUGIU")
            # diretoria em escrita / em rota de editar_cadastros
            if perm in ("editar_cadastros", "administrar"):
                r = dir_.req(M, p)
                reg(rota=f"{M} {caminho}", caso="diretoria", esperado=403, obtido=resumo(r),
                    flag="" if r.status_code == 403 else "FUGIU")
            if perm == "administrar":
                r = eng.req(M, p)
                reg(rota=f"{M} {caminho}", caso="engenharia_em_admin", esperado=403, obtido=resumo(r),
                    flag="" if r.status_code == 403 else "FUGIU")
            if M != "GET":
                r = adm.req(M, p, csrf=False)
                reg(rota=f"{M} {caminho}", caso="admin_sem_csrf", esperado=403, obtido=resumo(r),
                    flag="" if r.status_code == 403 else "FUGIU")
                r = adm.req(M, p, csrf=False, headers={"X-CSRF-Token": "errado"})
                reg(rota=f"{M} {caminho}", caso="admin_csrf_errado", esperado=403, obtido=resumo(r),
                    flag="" if r.status_code == 403 else "FUGIU")

    # ---- ids hostis (só rotas com id no caminho) ----
    hostis = [0, -1, 9223372036854775807, 9223372036854775808, 99999999999999999999, "abc", "1.5", "1e3", "%20"]
    for caminho, ops in spec["paths"].items():
        if "{" not in caminho:
            continue
        for metodo, op in ops.items():
            M = metodo.upper()
            corpo = montar_corpo(op, comps) if M != "GET" else {}
            for v in hostis:
                if "{formato}" in caminho:
                    p = caminho.replace("{formato}", "pdf")
                    p = preencher(p, v)
                else:
                    p = preencher(caminho, v)
                try:
                    r = adm.req(M, p, **corpo)
                except Exception as e:  # conexão caiu etc.
                    reg(rota=f"{M} {caminho}", caso=f"id={v}", obtido=f"EXC {e}", flag="EXC")
                    continue
                ok = r.status_code in (404, 422, 400, 405)
                reg(rota=f"{M} {caminho}", caso=f"id={v}", esperado="404/422", obtido=resumo(r, 160),
                    flag="" if ok else ("500" if r.status_code >= 500 else "FUGIU"))
    depois = contar_correio()
    print(f"correio simulado: antes={antes} depois={depois}")


if __name__ == "__main__":
    main()
