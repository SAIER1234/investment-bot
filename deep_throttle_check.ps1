
Write-Host "============================================"
Write-Host "  DEEP THROTTLE + REMAINING ISSUES CHECK"
Write-Host "============================================"

Write-Host ""
Write-Host "===== 1. CPU THROTTLING DETAILS ====="
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$throttleEvents = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Processor-Power'; Id=37; StartTime=$bootTime} -MaxEvents 20 -ErrorAction SilentlyContinue
Write-Host "Throttle events since boot: $($throttleEvents.Count)"
foreach ($e in $throttleEvents) {
    $msg = $e.Message
    if ($msg -match 'processor (\d+).*?group (\d+)') { Write-Host "  Core $($Matches[1]) Group $($Matches[2]) - $($e.TimeCreated)" }
    if ($msg -match '(\d+) seconds') { Write-Host "    Duration: $($Matches[1]) seconds" }
}

Write-Host ""
Write-Host "===== 2. POWER PLAN DETAILS ====="
powercfg /getactivescheme
Write-Host ""
Write-Host "Processor power management:"
powercfg /query SCHEME_CURRENT SUB_PROCESSOR 2>&1 | Select-String "maximum|minimum|Maximum|Minimum|throttle|Throttle|frequency|cooling|policy|Performance" -Context 0,0

Write-Host ""
Write-Host "===== 3. SYSTEM COOLING POLICY ====="
powercfg /query SCHEME_CURRENT SUB_PROCESSOR 2>&1 | Select-String "SystemCooling|systemcooling|Passive|passive|Active|active" -Context 0,0

Write-Host ""
Write-Host "===== 4. GPU DRIVER ====="
$gpu = Get-CimInstance Win32_VideoController | Where-Object { $PSItem.Name -match 'Intel' }
Write-Host "Name: $($gpu.Name)"
Write-Host "Version: $($gpu.DriverVersion)"
Write-Host "Date: $($gpu.DriverDate)"
Write-Host "VRAM: $([math]::Round($gpu.AdapterRAM/1MB,1)) MB"

Write-Host ""
Write-Host "===== 5. GPU TDR EVENTS ====="
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Display'} -MaxEvents 20 -ErrorAction SilentlyContinue | Where-Object { $PSItem.Id -in @(4101,4109,4114,4115,4117,4118,4120) } | Format-Table TimeCreated, Id, @{N='Short';E={($PSItem.Message -split '\n')[0]}} -AutoSize
Write-Host "(No TDR events = GPU stable)"

Write-Host ""
Write-Host "===== 6. REMAINING THIRD-PARTY SERVICES (automatic+running) ====="
Get-Service | Where-Object { $PSItem.StartType -eq 'Automatic' -and $PSItem.Status -eq 'Running' } | Where-Object { $PSItem.Name -notmatch '^(Win|Microsoft|App|CDP|Core|Crypt|Dcom|Device|Dhcp|Dnscache|DPS|EventLog|FontCache|gpsvc|IKEEXT|iphlpsvc|Lanman|lmhosts|mpssvc|MSDTC|MSiSCSI|Netlogon|Netman|nsi|PlugPlay|Power|ProfSvc|RasMan|Remote|Rpc|SamSs|Schedule|seclogon|SENS|SessionEnv|ShellHW|Spooler|SysMain|SystemEvents|Themes|TrkWks|UsoSvc|VaultSvc|W32Time|Wcmsvc|Wdi|Wecsvc|WEPHOSTSVC|WerSvc|WinHttp|Winmgmt|WlanSvc|wmiApSrv|WpnService|wuauserv|WSearch|bfe|Broker|camsvc|cbdhsvc|ClipSVC|DiagTrack|DusmSvc|EventSystem|fdPHost|FDResPub|FontCache3|hidserv|InstallService|KeyIso|LSM|Netman|NgcCtnrSvc|NgcSvc|PhoneSvc|PimIndexMaintenance|RmSvc|SCardSvr|ScDeviceEnum|SCPolicySvc|SDRSVC|SEMgrSvc|Sensor|SmsRouter|spectrum|StateRepository|StiSvc|StorSvc|TabletInputService|TapiSrv|TermService|TimeBroker|TokenBroker|tiledatamodelsvc|tzautoupdate|UdkUserSvc|UevAgentDriver|UmRdpService|UnistoreSvc|UserDataSvc|UserManager|VacSvc|vds|VSS|wcncsvc|WdiServiceHost|WdiSystemHost|WebClient|WFDSConMgrSvc|WEPHOSTSVC|wercplsupport|WiaRpc|WinRM|wisvc|wkssvc|wlidsvc|WManSvc|wmiApSrv|workfolderssvc|WPDBusEnum|WpnService|wscsvc|WSearch|WSService|Xbox)' } | Select-Object Name, DisplayName | Format-Table -AutoSize -Wrap

Write-Host ""
Write-Host "===== 7. WUDFRd DEVICES ====="
$wudfEvents = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-PnP'; Id=219; StartTime=$bootTime} -MaxEvents 20 -ErrorAction SilentlyContinue | Where-Object { $PSItem.Message -match 'WUDFRd' }
Write-Host "WUDFRd failures: $($wudfEvents.Count)"
foreach ($e in $wudfEvents | Select-Object -First 5) {
    $msg = $e.Message
    if ($msg -match 'ACPI\\\\([A-Z0-9]+)') { Write-Host "  Device: $($Matches[1])" }
    if ($msg -match 'STATUS_(\w+)') { Write-Host "  Error: $($Matches[1])" }
    Write-Host "  Time: $($e.TimeCreated)"
}

Write-Host ""
Write-Host "===== 8. SCHEDULED TASKS (non-Microsoft, active) ====="
Get-ScheduledTask | Where-Object { $PSItem.TaskPath -notmatch 'Microsoft' -and $PSItem.State -ne 'Disabled' } | Select-Object TaskName, State | Format-Table -AutoSize

Write-Host ""
Write-Host "===== 9. EDGE GPU ACCELERATION CHECK ====="
Write-Host "Edge is your main app. GPU acceleration status:"
$edgeGpu = Get-Process -Name msedge -ErrorAction SilentlyContinue
Write-Host "Edge processes: $($edgeGpu.Count)"
Write-Host "Total Edge memory: $([math]::Round(($edgeGpu | Measure-Object -Property WorkingSet64 -Sum).Sum/1MB,1)) MB"
Write-Host "If Edge GPU decode hangs, it can freeze the whole system."
Write-Host "Fix: edge://settings/system -> disable 'Use graphics acceleration'"

Write-Host ""
Write-Host "============================================"
Read-Host
