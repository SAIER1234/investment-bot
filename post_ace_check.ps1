
Write-Host "=== ACE Status After Reboot ==="

Write-Host ""
Write-Host "--- ACE drivers running ---"
$aceDrivers = Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match 'ACE' -and $PSItem.State -eq 'Running' }
Write-Host "Count: $($aceDrivers.Count)"
if ($aceDrivers.Count -gt 0) {
    foreach ($d in $aceDrivers) { Write-Host "  - $($d.Name) ($($d.StartMode))" }
} else {
    Write-Host "  NONE - ACE completely removed!"
}

Write-Host ""
Write-Host "--- ACE Filter Manager errors since boot ---"
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$filterErrors = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-FilterManager'; StartTime=$bootTime} -MaxEvents 50 -ErrorAction SilentlyContinue
$aceFilterErrors = $filterErrors | Where-Object { $PSItem.Message -match 'ACE' }
Write-Host "ACE filter errors: $($aceFilterErrors.Count)"
if ($aceFilterErrors.Count -eq 0) { Write-Host "  CLEAN!" }

Write-Host ""
Write-Host "--- ACE registry remnants ---"
$aceKeys = Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services" -ErrorAction SilentlyContinue | Where-Object { $PSItem.PSChildName -match 'ACE' }
Write-Host "Remaining ACE registry keys: $($aceKeys.Count)"
foreach ($k in $aceKeys) {
    $start = (Get-ItemProperty -Path $k.PSPath -Name "Start" -ErrorAction SilentlyContinue).Start
    Write-Host "  - $($k.PSChildName) Start=$start"
}

Write-Host ""
Write-Host "--- ACE folder ---"
if (Test-Path "C:\Program Files\AntiCheatExpert") {
    Write-Host "STILL EXISTS - manual delete needed"
} else {
    Write-Host "GONE - folder removed"
}

Write-Host ""
Write-Host "--- SbieDrv fix ---"
$sb = Get-Service -Name SbieDrv -ErrorAction SilentlyContinue
if ($sb) {
    Write-Host "Status: $($sb.Status) / $($sb.StartType)"
    $start = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\SbieDrv" -ErrorAction SilentlyContinue).Start
    Write-Host "Registry Start: $start (4=Disabled)"
}

Write-Host ""
Write-Host "--- What is consuming the nonpaged pool? ---"
Write-Host "Top processes by working set:"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 8 Name, @{N='WS_MB';E={[math]::Round($PSItem.WorkingSet64/1MB,1)}}, @{N='Priv_MB';E={[math]::Round($PSItem.PrivateMemorySize64/1MB,1)}} | Format-Table -AutoSize

Read-Host
