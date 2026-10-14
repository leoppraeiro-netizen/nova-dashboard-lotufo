# Snapshot do banco ANTES de um deploy que traz migracao (issue #75). Chamado pelo
# deploy.ps1 so' quando ha arquivo novo/alterado em backend/migrations.
#
# Usa a API de backup do SQLite (segura com WAL e com o servidor no ar), pelo Python
# passado em -Python (o do diretorio pinado). Nunca Copy-Item do .db: perderia o que
# ainda esta' no -wal. O banco de origem e' aberto so' para leitura.
#
# Grava em <destino>.tmp (nome que a rotacao do backup.py nao enxerga), roda
# PRAGMA integrity_check na copia e so' entao renomeia para
# <PastaBackups>\dashboard-PRE-<Rotulo>-<AAAAMMDD-HHMMSS>.db.
#
# Sucesso: escreve o caminho do snapshot na saida e sai com 0.
# Falha: imprime "BACKUP PRE-MIGRACAO FALHOU: <motivo>", apaga o que tiver gravado e
# sai com 1. Este arquivo fica so' com ASCII (sem BOM; o PowerShell 5.1 le como ANSI).
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Banco,
    [Parameter(Mandatory = $true)][string]$PastaBackups,
    [Parameter(Mandatory = $true)][string]$Python,
    [Parameter(Mandatory = $true)][string]$Rotulo
)
$ErrorActionPreference = "Stop"

# Vai pelo stdin do Python (python - <origem> <destino>): nada de aspas para o
# PowerShell 5.1 estragar na linha de comando.
$codigo = @'
import os, sqlite3, sys
from pathlib import Path

origem, parcial = sys.argv[1], sys.argv[2]

def so_leitura(caminho):
    return sqlite3.connect(Path(caminho).resolve().as_uri() + '?mode=ro', uri=True)

try:
    if not os.path.isfile(origem):
        sys.exit('banco nao encontrado: ' + origem)
    src = so_leitura(origem)
    dst = sqlite3.connect(parcial)
    try:
        src.backup(dst)
        # a copia sai como arquivo unico (sem -wal), pronta para restaurar
        modo = dst.execute('PRAGMA journal_mode=DELETE').fetchone()[0]
        if modo != 'delete':
            sys.exit('copia ficou em journal_mode=' + str(modo))
    finally:
        dst.close()
        src.close()
    chk = so_leitura(parcial)
    try:
        r = chk.execute('PRAGMA integrity_check').fetchone()
    finally:
        chk.close()
    if r is None or r[0] != 'ok':
        sys.exit('integrity_check da copia = ' + repr(r[0] if r else None))
except sqlite3.Error as e:
    sys.exit('sqlite: ' + str(e))
'@

$destino = Join-Path $PastaBackups ("dashboard-PRE-{0}-{1:yyyyMMdd-HHmmss}.db" -f $Rotulo, (Get-Date))
$parcial = "$destino.tmp"
try {
    if (-not (Test-Path -LiteralPath $Banco -PathType Leaf)) { throw "banco nao encontrado: $Banco" }
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "python nao encontrado: $Python" }
    New-Item -ItemType Directory -Path $PastaBackups -Force | Out-Null
    $codigo | & $Python - $Banco $parcial
    if ($LASTEXITCODE -ne 0) { throw "python saiu com codigo $LASTEXITCODE (motivo na linha acima)" }
    Move-Item -LiteralPath $parcial -Destination $destino
} catch {
    foreach ($sobra in @($parcial, "$parcial-journal", "$parcial-wal", "$parcial-shm")) {
        Remove-Item -LiteralPath $sobra -Force -ErrorAction SilentlyContinue
    }
    Write-Host "BACKUP PRE-MIGRACAO FALHOU: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
Write-Output $destino
exit 0
