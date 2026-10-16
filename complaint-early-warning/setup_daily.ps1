$ErrorActionPreference = 'Stop'
$pythonPath = (Get-Command python).Source
$scriptPath = Join-Path $PSScriptRoot 'pipeline.py'
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`" daily" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At '08:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$userName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $userName -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'ComplaintSignalsDaily' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Refresh CFPB complaints, SQL review signals and dashboard.' -Force
Write-Host 'Registered ComplaintSignalsDaily for 8 a.m. local time while logged in.'
