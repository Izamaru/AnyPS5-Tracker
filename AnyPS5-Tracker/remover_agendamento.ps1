$task = Get-ScheduledTask -TaskName 'AnyPS5 Tracker' -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName 'AnyPS5 Tracker' -Confirm:$false
    Write-Host 'Agendamento AnyPS5 Tracker removido.' -ForegroundColor Green
} else {
    Write-Host 'Nenhum agendamento encontrado.'
}
