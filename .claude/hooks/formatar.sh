#!/bin/sh
# Versao Mac/Linux de formatar.ps1 (mesma regra; os detalhes estao la'). Hook PostToolUse (Edit|Write):
#   .py em backend/          -> ruff check --fix;
#   .ts/.tsx em frontend/src -> oxlint no arquivo.
# Erro que a ferramenta nao consertou sozinha -> exit 2 com o erro no stderr (o Claude corrige).
# Ferramenta ausente -> exit 0 com aviso (o hook nunca trava a sessao por falta de ferramenta).
payload=$(cat)
py="$CLAUDE_PROJECT_DIR/backend/.venv/bin/python"
[ -x "$py" ] || py=python3
arquivo=$(printf '%s' "$payload" | "$py" -c 'import json, sys; print((json.load(sys.stdin).get("tool_input") or {}).get("file_path") or "")' 2>/dev/null)
[ -n "$arquivo" ] && [ -f "$arquivo" ] || exit 0

# Raiz do checkout do arquivo (o worktree ou o tree principal), para usar a ferramenta e a config dele.
pasta_arquivo=$(dirname "$arquivo")
raiz=$(git -C "$pasta_arquivo" rev-parse --show-toplevel 2>/dev/null) || exit 0
relativo="$(git -C "$pasta_arquivo" rev-parse --show-prefix)$(basename "$arquivo")"
# Tree principal (dono do .venv e do node_modules que os worktrees compartilham): pai do `.git` comum.
comum=$(git -C "$raiz" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
if [ -n "$comum" ]; then principal=$(dirname "$comum"); else principal=$raiz; fi

primeiro_existente() {
    for c in "$@"; do if [ -x "$c" ]; then echo "$c"; return; fi; done
}

case "$relativo" in
    backend/*.py)
        ferramenta=$(primeiro_existente "$raiz/backend/.venv/bin/ruff" "$principal/backend/.venv/bin/ruff")
        set -- check --fix --output-format concise "$arquivo"
        pasta="$raiz/backend" ;;
    frontend/src/*.ts | frontend/src/*.tsx)
        ferramenta=$(primeiro_existente "$raiz/frontend/node_modules/.bin/oxlint" "$principal/frontend/node_modules/.bin/oxlint")
        set -- --format unix "$arquivo"
        pasta="$raiz/frontend" ;;
    *) exit 0 ;;
esac

if [ -z "$ferramenta" ]; then
    echo "formatar.sh: ferramenta nao encontrada (ruff/oxlint) para $relativo; nada conferido." >&2
    exit 0
fi

saida=$(cd "$pasta" && "$ferramenta" "$@" 2>&1)
if [ $? -ne 0 ]; then
    echo "Lint encontrou erro que nao conserta sozinho em ${relativo}:" >&2
    printf '%s\n' "$saida" >&2
    exit 2
fi
exit 0
