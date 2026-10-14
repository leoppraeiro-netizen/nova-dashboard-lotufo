# Hook SessionStart / SubagentStart: se a sessao esta num worktree (pasta .claude\worktrees\<nome> ou
# qualquer checkout que nao seja o tree principal), cria as juncoes NTFS frontend\node_modules e
# backend\.venv apontando para as do tree principal, para nao baixar nem compilar nada por worktree.
# O Claude continua criando e removendo o worktree sozinho (nao usamos WorktreeCreate, que substituiria
# a criacao dele). Tambem roda a mao, sem stdin, de dentro do worktree:
#   powershell -NoProfile -ExecutionPolicy Bypass -File <principal>\.claude\hooks\preparar-worktree.ps1
# CUIDADO: nunca apagar um worktree com Remove-Item -Recurse no PowerShell 5.1 (ele segue a juncao e
# apaga o node_modules/.venv do tree principal). Usar `git worktree remove` ou deixar o Claude remover.
[Console]::InputEncoding = [Text.Encoding]::UTF8
$cwd = (Get-Location).Path
if (-not [Console]::IsInputRedirected -or [Console]::In.Peek() -eq -1) { $payload = $null }
else { try { $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json } catch { $payload = $null } }
if ($payload -and $payload.cwd) { $cwd = $payload.cwd }
Set-Location -LiteralPath $cwd

$raiz = (git rev-parse --show-toplevel 2>$null) -replace '/', '\'
if (-not $raiz) { exit 0 }
# Pre-commit versionado (.githooks/pre-commit): ruff check e tsc so' no que esta' no commit. A config e'
# compartilhada entre o tree principal e os worktrees, entao basta ligar uma vez, em qualquer um.
if ((git config --get core.hooksPath 2>$null) -ne '.githooks') { git config core.hooksPath .githooks }
$comum = (git rev-parse --path-format=absolute --git-common-dir 2>$null) -replace '/', '\'
$principal = if ($comum) { Split-Path -Parent $comum } else { Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }   # <principal>\.claude\hooks
if ($raiz -ieq $principal) { exit 0 }   # tree principal: so' o hooksPath acima

foreach ($rel in @('frontend\node_modules', 'backend\.venv')) {
    $link = "$raiz\$rel"
    $alvo = "$principal\$rel"
    if ((Test-Path -LiteralPath $alvo) -and -not (Test-Path -LiteralPath $link)) {
        cmd /c mklink /J "$link" "$alvo" 2>&1 | ForEach-Object { [Console]::Error.WriteLine("$_") }
    }
}
exit 0
