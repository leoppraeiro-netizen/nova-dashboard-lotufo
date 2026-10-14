# Conferencia de ACL NTFS compartilhada pelos scripts de producao.
# Uso: . (Join-Path $PSScriptRoot "comum_acl.ps1")
#
# POR QUE VALIDAR DEPOIS DE APLICAR O ICACLS:
# "icacls <pasta> /inheritance:r /grant:r <SID>:F" faz duas coisas -- apaga as ACEs
# HERDADAS e SUBSTITUI as ACEs dos SIDs que voce nomeia. Ele nao encosta em ACE
# EXPLICITA de um terceiro. Se a pasta ja tinha, gravada a mao, "Usuarios: Modificar",
# essa ACE sobrevive aos dois parametros: o comando devolve exit 0, a mensagem diz
# "processados com exito", e a pasta continua aberta. So /remove ou /reset a tiram.
# Dai a validacao explicita das funcoes abaixo, em vez de confiar no codigo de saida.

$SID_SISTEMA              = "S-1-5-18"       # NT AUTHORITY\SYSTEM
$SID_ADMINISTRADORES      = "S-1-5-32-544"   # BUILTIN\Administrators ("Administradores" no pt-BR)
$SID_CRIADOR_PROPRIETARIO = "S-1-3-0"        # CREATOR OWNER (placeholder herdado, nao e' conta)
$SID_TRUSTEDINSTALLER     = "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"

# Direitos que permitem ALTERAR o conteudo, apagar, ou reescrever a propria ACL.
# Leitura pura fica de fora de proposito: o risco tratado aqui e' o de TROCAR o
# codigo/venv que depois roda como SYSTEM, nao o de le-lo.
# GENERIC_ALL/GENERIC_WRITE entram porque ACLs antigas ainda aparecem nessa forma.
$DIREITOS_DE_ESCRITA = (
    [int][System.Security.AccessControl.FileSystemRights]::Write -bor
    [int][System.Security.AccessControl.FileSystemRights]::Delete -bor
    [int][System.Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
    [int][System.Security.AccessControl.FileSystemRights]::ChangePermissions -bor
    [int][System.Security.AccessControl.FileSystemRights]::TakeOwnership -bor
    0x10000000 -bor 0x40000000
)

function ConvertTo-SidTexto {
    # Comparar por SID, nunca por nome: o Windows desta maquina e' pt-BR
    # ("SISTEMA", "Administradores", "Usuarios") e nome traduzido nao casa.
    param($Identidade)
    if ($Identidade -is [System.Security.Principal.SecurityIdentifier]) { return $Identidade.Value }
    try { return $Identidade.Translate([System.Security.Principal.SecurityIdentifier]).Value }
    catch { return $Identidade.Value }   # SID orfao (conta apagada): ja vem como texto
}

function Get-EscritoresIndevidos {
    # Lista, em texto legivel, os principais que podem ALTERAR $Caminho e nao
    # constam em $SidsConfiaveis. Array vazio = caminho saudavel.
    param(
        [Parameter(Mandatory = $true)][string]$Caminho,
        [Parameter(Mandatory = $true)][string[]]$SidsConfiaveis
    )
    $achados = @()
    $acl = Get-Acl -LiteralPath $Caminho
    foreach ($regra in $acl.Access) {
        if ($regra.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) { continue }
        if ((([int]$regra.FileSystemRights) -band $DIREITOS_DE_ESCRITA) -eq 0) { continue }
        $sid = ConvertTo-SidTexto $regra.IdentityReference
        if ($SidsConfiaveis -contains $sid) { continue }
        $achados += ("{0} (SID {1}) com '{2}'" -f $regra.IdentityReference.Value, $sid, $regra.FileSystemRights)
    }
    return @($achados)
}

function Get-DonoIndevido {
    # Devolve o texto do problema se o DONO de $Caminho nao estiver em $SidsConfiaveis,
    # ou $null se estiver.
    # POR QUE O DONO IMPORTA: o proprietario de um objeto NTFS tem WRITE_DAC implicito
    # -- mesmo sem nenhuma ACE em nome dele, pode reescrever a ACL e se reconceder
    # tudo a qualquer momento. Auditar so a DACL e' fechar a porta e deixar a chave
    # pendurada nela: um usuario comum dono da pasta desfaz o endurecimento sozinho.
    param(
        [Parameter(Mandatory = $true)][string]$Caminho,
        [Parameter(Mandatory = $true)][string[]]$SidsConfiaveis
    )
    $acl = Get-Acl -LiteralPath $Caminho
    # GetOwner([SecurityIdentifier]): compara por SID, como no resto do arquivo, e
    # nao quebra com SID orfao (conta apagada), que nao traduz para nome.
    $sid = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
    if ($SidsConfiaveis -contains $sid) { return $null }
    return ("dono e' {0} (SID {1}) -- dono reescreve a ACL quando quiser" -f $acl.Owner, $sid)
}

function Set-DonoAdministradores {
    # Passa a propriedade de $Caminho para Administradores (parte do endurecimento,
    # junto do icacls de DACL). Sem isto, fechar a DACL nao adianta: ver Get-DonoIndevido.
    #
    # -Recursivo (/T): sem ele so a PASTA troca de dono. Arquivos que ja existiam la
    # dentro -- o proprio .db, backups antigos -- continuam com o dono anterior, e dono
    # reescreve a DACL do arquivo quando quiser (WRITE_DAC implicito). Endurecer so o
    # container deixa o conteudo aberto.
    param(
        [Parameter(Mandatory = $true)][string]$Caminho,
        [switch]$Recursivo
    )
    if ($Recursivo) { & icacls $Caminho /setowner ("*" + $SID_ADMINISTRADORES) /T | Out-Null }
    else            { & icacls $Caminho /setowner ("*" + $SID_ADMINISTRADORES)    | Out-Null }
    if ($LASTEXITCODE -ne 0) { throw "Falha ao definir Administradores como dono de $Caminho (rodar como administrador)." }
}

function Assert-AclSomenteSistemaEAdmins {
    # Falha alto se, DEPOIS do endurecimento, o caminho ainda tiver heranca ligada,
    # dono fora de SYSTEM/Administradores, ou qualquer permissao concedida fora deles.
    param([Parameter(Mandatory = $true)][string]$Caminho)

    $acl = Get-Acl -LiteralPath $Caminho
    $problemas = @()

    $dono = Get-DonoIndevido -Caminho $Caminho -SidsConfiaveis @($SID_SISTEMA, $SID_ADMINISTRADORES)
    if ($null -ne $dono) { $problemas += $dono }

    foreach ($regra in $acl.Access) {
        if ($regra.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) { continue }
        $sid = ConvertTo-SidTexto $regra.IdentityReference
        if ($sid -eq $SID_SISTEMA -or $sid -eq $SID_ADMINISTRADORES) { continue }
        # ACE herdada de SYSTEM/Administradores e' o estado esperado de um ARQUIVO criado
        # dentro de pasta ja endurecida (chave.pem, o .db copiado): so a heranca de
        # principal fora dos dois e' porta aberta.
        if ($regra.IsInherited) {
            $problemas += ("heranca ainda ligada: ACE herdada de {0}" -f $regra.IdentityReference.Value)
            continue
        }
        $problemas += ("{0} (SID {1}) ainda tem '{2}'" -f $regra.IdentityReference.Value, $sid, $regra.FileSystemRights)
    }

    if ($problemas.Count -gt 0) {
        $lista = ($problemas | ForEach-Object { "  - $_" }) -join [Environment]::NewLine
        throw @"
A ACL de $Caminho continua aberta DEPOIS do endurecimento:
$lista

Motivo: '/inheritance:r /grant:r' nao apaga ACE explicita de terceiro -- so troca a dos SIDs citados.
Remova a ACE a mao (como administrador) e rode este script de novo:
  icacls "$Caminho" /remove:g "<principal listado acima>" /T
  icacls "$Caminho" /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F"

Se o problema for o DONO, tome a propriedade (como administrador):
  icacls "$Caminho" /setowner "*S-1-5-32-544"
"@
    }
}
