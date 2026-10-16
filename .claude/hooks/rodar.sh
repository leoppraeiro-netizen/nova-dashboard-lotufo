#!/bin/sh
# Escolhe a versao do hook pelo sistema. O Claude roda o hook pelo Git Bash no Windows e por `sh -c` no Mac,
# entao `sh rodar.sh <nome>` funciona nos dois:
#   Windows (powershell.exe no PATH) -> <nome>.ps1, exatamente como antes;
#   Mac/Linux                        -> <nome>.sh, a mesma regra em sh.
# O stdin (payload do hook) e o codigo de saida passam direto pelo exec.
dir=$(dirname "$0")
if command -v powershell.exe >/dev/null 2>&1; then
    exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$dir/$1.ps1"
fi
exec sh "$dir/$1.sh"
