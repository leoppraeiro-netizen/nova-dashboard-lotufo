#!/bin/sh
# Versao Mac/Linux de preparar-worktree.ps1 (mesma regra; os detalhes estao la'). Hook SessionStart /
# SubagentStart: liga o core.hooksPath e, num worktree, cria os links simbolicos frontend/node_modules e
# backend/.venv apontando para os do tree principal, para nao baixar nem compilar nada por worktree.
# Tambem roda a mao, sem stdin, de dentro do worktree:
#   sh <principal>/.claude/hooks/preparar-worktree.sh
if [ ! -t 0 ]; then
    cwd=$(python3 -c 'import json, sys; print(json.load(sys.stdin).get("cwd") or "")' 2>/dev/null)
    [ -n "$cwd" ] && cd "$cwd"
fi

raiz=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
# Pre-commit versionado (.githooks/pre-commit). A config e' compartilhada entre o tree principal e os
# worktrees, entao basta ligar uma vez, em qualquer um.
[ "$(git config --get core.hooksPath)" = ".githooks" ] || git config core.hooksPath .githooks
comum=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
if [ -n "$comum" ]; then principal=$(dirname "$comum"); else principal=$(cd "$(dirname "$0")/../.." && pwd -P); fi
[ "$raiz" = "$principal" ] && exit 0   # tree principal: so' o hooksPath acima

for rel in frontend/node_modules backend/.venv; do
    link="$raiz/$rel"
    alvo="$principal/$rel"
    if [ -e "$alvo" ] && [ ! -e "$link" ] && [ ! -L "$link" ]; then
        ln -s "$alvo" "$link"
    fi
done
exit 0
