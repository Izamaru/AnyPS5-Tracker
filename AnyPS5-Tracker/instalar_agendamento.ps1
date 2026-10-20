[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateRange(5, 1440)]
    [int]$IntervaloMinutos = 5,
    [string]$PythonExe
)

$ErrorActionPreference = 'Stop'
$dir = $PSScriptRoot

# Valida o interpretador: aliases da Microsoft Store podem existir sem Python instalado.
if ($PythonExe) {
    $candidates = @(@{ Exe = $PythonExe; Prefix = @() })
} else {
    $candidates = @()
    foreach ($name in @('py', 'python', 'python3')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            $prefix = @()
            if ($name -eq 'py') { $prefix = @('-3') }
            $candidates += @{ Exe = $command.Source; Prefix = $prefix }
        }
    }
    # Fallback para o Python ja instalado pelo Codex neste computador.
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { $candidates += @{ Exe = $bundled; Prefix = @() } }
}
$resolvedPython = $null
foreach ($candidate in $candidates) {
    try {
        $probeArgs = @($candidate.Prefix) + @('-c', 'import sys; assert sys.version_info >= (3, 10); print(sys.executable)')
        $result = & $candidate.Exe @probeArgs 2>$null
        if ($LASTEXITCODE -eq 0 -and $result -and (Test-Path -LiteralPath ([string]$result))) {
            $resolvedPython = [string]$result
            break
        }
    } catch { continue }
}
if (-not $resolvedPython) { throw 'Python 3.10+ nao encontrado. Instale Python ou informe -PythonExe com o caminho do executavel.' }

$runner = Join-Path $dir 'executar_agendado.ps1'
$arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $runner + '" -PythonExe "' + $resolvedPython + '"'
$powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action = New-ScheduledTaskAction -Execute $powershellExe -Argument $arguments -WorkingDirectory $dir
# Sem RepetitionDuration, a repeticao continua por tempo indeterminado.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervaloMinutos)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
if ($PSCmdlet.ShouldProcess('AnyPS5 Tracker', "Agendar coleta a cada $IntervaloMinutos minutos e executar agora")) {
    Register-ScheduledTask -TaskName 'AnyPS5 Tracker' -Description "Coleta dados do AnyPS5 a cada $IntervaloMinutos minutos, sem notificacoes externas." -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    Start-ScheduledTask -TaskName 'AnyPS5 Tracker'
    Write-Host "Tracker ativado a cada $IntervaloMinutos minutos. Primeira coleta iniciada." -ForegroundColor Green
    Write-Host 'O painel aberto recarrega sozinho a cada 5 minutos. Logs em dados\ultima-execucao.log.'
}
