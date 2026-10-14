# Hook PostToolUse (Edit|Write): confere o arquivo que o Claude acabou de editar.
#   .py em backend/       -> ruff check --fix (regras do backend/pyproject.toml). Sem `ruff format`:
#                            ele reformataria 157 de 161 arquivos (medido em 11/10/2026).
#   .ts/.tsx em frontend/src -> oxlint no arquivo.
# Erro que a ferramenta nao consertou sozinha -> exit 2 com o erro no stderr (o Claude corrige).
# Ferramenta ausente -> exit 0 com aviso (o hook nunca trava a sessao por falta de ferramenta).
[Console]::InputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
Set-Location -LiteralPath $payload.cwd

$arquivo = $payload.tool_input.file_path
if (-not $arquivo -or -not (Test-Path -LiteralPath $arquivo -PathType Leaf)) { exit 0 }

# Raiz do checkout do arquivo (o worktree ou o tree principal), para usar a ferramenta e a config dele.
$raiz = git -C (Split-Path -LiteralPath $arquivo) rev-parse --show-toplevel 2>$null
if (-not $raiz) { exit 0 }
$raiz = $raiz -replace '/', '\'
$relativo = $arquivo.Substring($raiz.Length).TrimStart('\', '/') -replace '/', '\'
# Tree principal (dono do .venv e do node_modules que os worktrees compartilham): pai do `.git` comum.
$comum = (git -C $raiz rev-parse --path-format=absolute --git-common-dir 2>$null) -replace '/', '\'
$principal = if ($comum) { Split-Path -Parent $comum } else { $raiz }

function Primeiro-Existente($caminhos) {
    foreach ($c in $caminhos) { if (Test-Path -LiteralPath $c) { return $c } }
    return $null
}

if ($relativo -like 'backend\*' -and $relativo -like '*.py') {
    $ferramenta = Primeiro-Existente @("$raiz\backend\.venv\Scripts\ruff.exe", "$principal\backend\.venv\Scripts\ruff.exe")
    $argumentos = @('check', '--fix', '--output-format', 'concise', $arquivo)
    $pasta = "$raiz\backend"
} elseif ($relativo -like 'frontend\src\*' -and ($relativo -like '*.ts' -or $relativo -like '*.tsx')) {
    $ferramenta = Primeiro-Existente @("$raiz\frontend\node_modules\.bin\oxlint.cmd", "$principal\frontend\node_modules\.bin\oxlint.cmd")
    $argumentos = @('--format', 'unix', $arquivo)
    $pasta = "$raiz\frontend"
} else {
    exit 0
}

if (-not $ferramenta) {
    [Console]::Error.WriteLine("formatar.ps1: ferramenta nao encontrada (ruff/oxlint) para $relativo; nada conferido.")
    exit 0
}

Set-Location -LiteralPath $pasta
# ErrorRecord (linha do stderr no PowerShell 5.1): usar a mensagem; "$_" de linha vazia vira o nome do tipo.
$saida = & $ferramenta @argumentos 2>&1 | ForEach-Object { if ($_ -is [Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" } }
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("Lint encontrou erro que nao conserta sozinho em ${relativo}:")
    [Console]::Error.WriteLine(($saida -join "`n"))
    exit 2
}
exit 0
