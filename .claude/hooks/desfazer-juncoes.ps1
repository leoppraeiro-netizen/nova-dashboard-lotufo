# Hook WorktreeRemove: antes de o Claude remover o worktree, desfaz as juncoes frontend\node_modules e
# backend\.venv (criadas por preparar-worktree.ps1). `rmdir` sem /s apaga so o vinculo, nunca o destino.
# Sem isso o `git worktree remove` deixa a casca da pasta no disco e o mesmo nome nao pode ser reusado.
[Console]::InputEncoding = [Text.Encoding]::UTF8
try { $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json } catch { exit 0 }
$alvo = $payload.worktree_path
if (-not $alvo) { $alvo = $payload.cwd }
if (-not $alvo) { exit 0 }
$alvo = [IO.Path]::GetFullPath($alvo)
if ($alvo -notmatch '\\\.claude\\worktrees\\[^\\]+$') { exit 0 }   # so dentro de .claude\worktrees
foreach ($rel in @('frontend\node_modules', 'backend\.venv')) {
    $link = "$alvo\$rel"
    if (Test-Path -LiteralPath $link) {
        $item = Get-Item -LiteralPath $link -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { cmd /c rmdir "$link" }
    }
}
exit 0
