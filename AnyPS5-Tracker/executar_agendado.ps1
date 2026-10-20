param([Parameter(Mandatory)][string]$PythonExe)
$ErrorActionPreference = 'Stop'
$dataDir = Join-Path $PSScriptRoot 'dados'
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
$log = Join-Path $dataDir 'ultima-execucao.log'
$errorLog = Join-Path $dataDir 'ultima-execucao-erros.log'
try {
    $env:PYTHONIOENCODING = 'utf-8'
    # Cada execucao substitui o log; o historico de medicoes continua no JSONL.
    $arguments = '"' + (Join-Path $PSScriptRoot 'tracker.py') + '" --once --no-notify'
    $process = Start-Process -FilePath $PythonExe -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $log -RedirectStandardError $errorLog
    if ((Get-Item -LiteralPath $errorLog).Length -gt 0) {
        Get-Content -LiteralPath $errorLog -Encoding utf8 | Add-Content -LiteralPath $log -Encoding utf8
    }
    if ($process.ExitCode -ne 0) { exit $process.ExitCode }
} catch {
    $_ | Out-File -LiteralPath $log -Append -Encoding utf8
    exit 1
}
exit 0
