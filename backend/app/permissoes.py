from fastapi import Depends, HTTPException

from app.api_auth import exigir_csrf, usuario_atual

# frozenset: a matriz de permissoes e' constante de modulo e nao pode ser mutada
# por engano em tempo de execucao (um .add() num set aqui daria permissao a todo
# mundo, silenciosamente e sem deixar rastro na auditoria).
PERFIS: dict[str, frozenset[str]] = {
    "diretoria": frozenset({"ver_paineis"}),
    "engenharia": frozenset({"ver_paineis", "editar_cadastros"}),
    "admin": frozenset({"ver_paineis", "editar_cadastros", "editar_config_fiscal", "administrar"}),
}

_VAZIO: frozenset[str] = frozenset()

def tem(perfil: str, permissao: str) -> bool:
    return permissao in PERFIS.get(perfil, _VAZIO)

def exigir(permissao: str, com_csrf: bool = True):
    """Devolve uma dependency que exige sessao valida + a permissao informada.

    com_csrf=True (padrao) tambem valida o header X-CSRF-Token -- use em rotas
    que escrevem. Em leituras (GET), passar com_csrf=False.
    """
    base = exigir_csrf if com_csrf else usuario_atual

    def dep(usuario: dict = Depends(base)) -> dict:
        if not tem(usuario["perfil"], permissao):
            raise HTTPException(403, f"Permissão necessária: {permissao}")
        return usuario

    return dep
