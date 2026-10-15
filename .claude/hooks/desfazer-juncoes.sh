#!/bin/sh
# Versao Mac/Linux de desfazer-juncoes.ps1. Hook WorktreeRemove: antes de o Claude remover o worktree, apaga
# os links simbolicos frontend/node_modules e backend/.venv (criados por preparar-worktree.sh). `rm` num
# link simbolico apaga so' o link, nunca o destino.
alvo=$(python3 -c 'import json, sys; d = json.load(sys.stdin); print(d.get("worktree_path") or d.get("cwd") or "")' 2>/dev/null)
case "$alvo" in
    */.claude/worktrees/*/*) exit 0 ;;   # so' a pasta do worktree, nada abaixo dela
    */.claude/worktrees/?*) ;;
    *) exit 0 ;;
esac
for rel in frontend/node_modules backend/.venv; do
    [ -L "$alvo/$rel" ] && rm "$alvo/$rel"
done
exit 0
