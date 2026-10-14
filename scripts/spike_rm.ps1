# spike_rm.ps1 - Task 3 (Fase 0): provar o conduto API + Consulta SQL do RM fim a fim.
# Credenciais pedidas em tempo de execucao (Get-Credential) - NUNCA gravadas em lugar nenhum.
# Saida: um JSON por consulta em %TEMP%\rm-spike-saida\ (fora do repositorio).
#
# Uso:
#   .\spike_rm.ps1                       # executa DASH01
#   .\spike_rm.ps1 -Consultas DASH01,DASH02,DASH03,DASH04
param(
    [string[]]$Consultas = @('DASH01', 'DASH02', 'DASH03', 'DASH04'),
    [string]$Servidor = '',   # servidor:porta da API do RM (fora do repositorio)
    [string]$Coligada = '0',
    # 'F' = RM Fluxus: aplicacao usada no cadastro (a instalacao nao licencia a aplicacao Global 'G')
    [string]$Sistema  = 'F',
    [string]$SaidaDir = (Join-Path $env:TEMP 'rm-spike-saida')
)

$ErrorActionPreference = 'Stop'
if (-not $Servidor) { throw 'Informe -Servidor (servidor:porta da API do RM).' }
# Com "powershell -File", um argumento "A,B" chega como string unica - separar aqui:
$Consultas = $Consultas | ForEach-Object { $_ -split ',' } | Where-Object { $_ }
if (-not (Test-Path $SaidaDir)) { New-Item -ItemType Directory -Path $SaidaDir | Out-Null }

$cred = Get-Credential -Message 'Usuario RM (a senha nao e gravada)'
$pair = '{0}:{1}' -f $cred.UserName, $cred.GetNetworkCredential().Password
$auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair))
$headers = @{ Authorization = "Basic $auth" }
$pair = $null

foreach ($codigo in $Consultas) {
    $url = "http://$Servidor/api/framework/v1/consultaSQLServer/RealizaConsulta/$codigo/$Coligada/$Sistema"
    $arq = Join-Path $SaidaDir "$codigo.json"
    Write-Host "==> $codigo : $url"
    try {
        $r = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 120
        $json = $r | ConvertTo-Json -Depth 8
        [IO.File]::WriteAllText($arq, $json, (New-Object Text.UTF8Encoding $true))
        $n = if ($r -is [array]) { $r.Count } elseif ($null -ne $r) { 1 } else { 0 }
        Write-Host ("    OK - {0} registro(s). Salvo em {1}" -f $n, $arq) -ForegroundColor Green
    }
    catch {
        $status = ''
        $corpo  = ''
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
            try {
                $sr = New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())
                $corpo = $sr.ReadToEnd()
                $sr.Close()
            } catch {}
        }
        $erro = @{ consulta = $codigo; url = $url; status = $status; erro = $_.Exception.Message; corpo = $corpo } | ConvertTo-Json -Depth 4
        [IO.File]::WriteAllText($arq, $erro, (New-Object Text.UTF8Encoding $true))
        Write-Host ("    FALHOU - HTTP {0}: {1}" -f $status, $_.Exception.Message) -ForegroundColor Red
        if ($corpo) { Write-Host ("    Corpo: {0}" -f $corpo.Substring(0, [Math]::Min(500, $corpo.Length))) -ForegroundColor Yellow }
        if ($status -eq 401) { Write-Host '    Dica: usuario/senha do RM (nao e o login do Windows).' }
        if ($status -eq 404) { Write-Host '    Dica: conferir codigo/coligada/sistema exatamente como cadastrados na consulta.' }
    }
}
Write-Host ''
Write-Host ("Saidas em: {0}" -f $SaidaDir)
