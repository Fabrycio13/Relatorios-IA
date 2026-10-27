<#
.SYNOPSIS
    Gerenciador da Tarefa Agendada no Windows para o Diario de Engenharia.

.DESCRIPTION
    Instala, remove ou consulta a tarefa agendada no Windows Task Scheduler com:
    - Gatilho diario pontual as 08:00 AM
    - Gatilho de Logon (se ligar a maquina apos as 08:00)
    - Execucao silenciosa sem janelas de terminal via VBScript
    - Retentativa automatica de 5 em 5 minutos caso a maquina esteja sem internet ao ligar

.PARAMETER Install
    Cria ou atualiza a tarefa agendada 'Relatorio_Diario_IA'.

.PARAMETER Uninstall
    Remove a tarefa agendada do sistema.

.PARAMETER Status
    Exibe o status, horarios de execucao e resultado da tarefa.

.PARAMETER RunNow
    Dispara a execucao da tarefa imediatamente.

.EXAMPLE
    .\scripts\setup_task.ps1 -Install
    .\scripts\setup_task.ps1 -Status
#>

[CmdletBinding(DefaultParameterSetName = "Status")]
param (
    [Parameter(ParameterSetName = "Install")]
    [switch]$Install,

    [Parameter(ParameterSetName = "Uninstall")]
    [switch]$Uninstall,

    [Parameter(ParameterSetName = "Status")]
    [switch]$Status,

    [Parameter(ParameterSetName = "RunNow")]
    [switch]$RunNow
)

$TaskName = "Relatorio_Diario_IA"
$ProjectDir = (Get-Item -Path "$PSScriptRoot\..").FullName
$VbsScript = Join-Path $ProjectDir "scripts\executar_silencioso.vbs"

if (-not (Test-Path $VbsScript)) {
    Write-Error "Arquivo de execucao silenciosa nao encontrado em: $VbsScript"
    exit 1
}

# --- UNINSTALL ---
if ($Uninstall) {
    Write-Host "Removendo tarefa agendada '$TaskName'..." -ForegroundColor Yellow
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Tarefa '$TaskName' removida com sucesso!" -ForegroundColor Green
    } else {
        Write-Host "A tarefa '$TaskName' nao esta cadastrada no Windows." -ForegroundColor Cyan
    }
    exit 0
}

# --- INSTALL ---
if ($Install) {
    Write-Host "Configurando tarefa agendada '$TaskName'..." -ForegroundColor Cyan
    Write-Host "   Diretorio do projeto : $ProjectDir"
    Write-Host "   Script silencioso    : $VbsScript"

    $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsScript`"" -WorkingDirectory $ProjectDir

    $trigDaily = New-ScheduledTaskTrigger -Daily -At 08:00AM
    $trigLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 5)

    $taskDesc = "Geracao e envio diario automatizado do Diario de Engenharia - IA e Coding Agents"
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger @($trigDaily, $trigLogon) `
        -Settings $settings `
        -Description $taskDesc `
        -Force | Out-Null

    Write-Host "Tarefa '$TaskName' instalada/atualizada com sucesso!" -ForegroundColor Green
    Write-Host "   - Disparo 1: Diario as 08:00 AM"
    Write-Host "   - Disparo 2: Ao fazer login no Windows se ligar o PC apos as 08:00"
    Write-Host "   - Retentativas: 3 tentativas a cada 5 minutos caso esteja sem internet"
    exit 0
}

# --- RUN NOW ---
if ($RunNow) {
    Write-Host "Disparando tarefa '$TaskName' agora..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 2
    $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Host "Tarefa iniciada. Ultima execucao: $($info.LastRunTime)" -ForegroundColor Green
    exit 0
}

# --- STATUS (Default) ---
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Host "A tarefa '$TaskName' NAO esta instalada." -ForegroundColor Yellow
    Write-Host "Execute '.\scripts\setup_task.ps1 -Install' para configura-la." -ForegroundColor Cyan
    exit 0
}

$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " STATUS DA TAREFA AGENDADA: $TaskName" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Estado atual           : $($task.State)"
Write-Host " Comando                : $($task.Actions[0].Execute) $($task.Actions[0].Arguments)"
Write-Host " Diretorio              : $($task.Actions[0].WorkingDirectory)"
Write-Host " Gatilhos configurados  : $($task.Triggers.Count) (Diario 08:00 AM + Ao Logon)"
Write-Host " Iniciar se perdeu hora : $($task.Settings.StartWhenAvailable)"
Write-Host " Retentativas em falha  : $($task.Settings.RestartCount)x a cada $($task.Settings.RestartInterval)"
Write-Host " Ultima execucao        : $($info.LastRunTime)"
Write-Host " Codigo ultimo retorno  : $($info.LastTaskResult)"
Write-Host " Proxima execucao       : $($info.NextRunTime)"
Write-Host "==========================================================" -ForegroundColor Cyan
