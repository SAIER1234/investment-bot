
Write-Host "============================================"
Write-Host "  COMPLETE SYSTEM HEALTH AUDIT"
Write-Host "  $(Get-Date)"
Write-Host "============================================"

Write-Host ""
Write-Host "===== 1. CRASHES ====="
$all41 = Get-WinEvent -FilterHashtable @{LogName='System'; Id=41} -MaxEvents 20 -ErrorAction SilentlyContinue
$recent41 = $all41 | Where-Object { $PSItem.TimeCreated -gt (Get-Date).AddDays(-3) }
Write-Host "Event 41 (force shutdown) total: $($all41.Count)"
Write-Host "Event 41 last 3 days: $($recent41.Count)"
if ($recent41.Count -eq 0) { Write-Host "  NO crashes in 3 days" }
else { foreach ($e in $recent41) { Write-Host "  ! $($e.TimeCreated)" } }

Write-Host ""
Write-Host "===== 2. UPTIME ====="
$uptime = [math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours, 1)
Write-Host "Uptime: $uptime hours"

Write-Host ""
Write-Host "===== 3. MEMORY ====="
$os = Get-CimInstance Win32_OperatingSystem
$freeMem = [math]::Round($os.FreePhysicalMemory/1MB, 1)
$totalMem = [math]::Round($os.TotalVisibleMemorySize/1MB, 1)
Write-Host "Free: $freeMem GB / $totalMem GB ($([math]::Round($freeMem/$totalMem*100,1))%)"

Write-Host ""
Write-Host "===== 4. NONPAGED POOL ====="
$mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
$np = [math]::Round($mem.PoolNonpagedBytes/1MB, 1)
$pp = [math]::Round($mem.PoolPagedBytes/1MB, 1)
Write-Host "Nonpaged: $np MB"
Write-Host "Paged: $pp MB"
if ($np -lt 500) { Write-Host "  EXCELLENT" }
elseif ($np -lt 700) { Write-Host "  GOOD" }
else { Write-Host "  ELEVATED - monitor" }

Write-Host ""
Write-Host "===== 5. ERRORS SINCE BOOT ====="
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$errors = Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=$bootTime} -MaxEvents 50 -ErrorAction SilentlyContinue
Write-Host "Critical/Error events: $($errors.Count)"
if ($errors.Count -gt 0) {
    $errors | Group-Object ProviderName | Sort-Object Count -Descending | Format-Table Count, Name -AutoSize
}

Write-Host ""
Write-Host "===== 6. WARNINGS SINCE BOOT ====="
$warnings = Get-WinEvent -FilterHashtable @{LogName='System'; Level=3; StartTime=$bootTime} -MaxEvents 50 -ErrorAction SilentlyContinue
$groupedWarnings = $warnings | Group-Object ProviderName | Sort-Object Count -Descending
Write-Host "Warning events: $($warnings.Count)"
foreach ($g in $groupedWarnings | Select-Object -First 10) {
    Write-Host "  $($g.Count)x $($g.Name)"
}

Write-Host ""
Write-Host "===== 7. KASPERSKY ====="
$kl = (Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match '^kl' -and $PSItem.State -eq 'Running' } | Measure-Object).Count
Write-Host "Kaspersky drivers: $kl"

Write-Host ""
Write-Host "===== 8. ACE ====="
$aceDrv = (Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match 'ACE' -and $PSItem.State -eq 'Running' } | Measure-Object).Count
$aceFlt = (Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-FilterManager'; StartTime=$bootTime} -MaxEvents 20 -ErrorAction SilentlyContinue | Where-Object { $PSItem.Message -match 'ACE' } | Measure-Object).Count
Write-Host "ACE drivers running: $aceDrv"
Write-Host "ACE filter events: $aceFlt"

Write-Host ""
Write-Host "===== 9. HUAWEI ====="
$huaweiProcs = @('HiConnectivityService','HwPCCoreService','HwDistributedMainService','HWSyncService','MBAMainService')
$huaweiRunning = 0
foreach ($n in $huaweiProcs) {
    $s = Get-Service -Name $n -ErrorAction SilentlyContinue
    if ($s -and $s.Status -ne 'Stopped') { $huaweiRunning++ }
}
Write-Host "Huawei services running: $huaweiRunning"

Write-Host ""
Write-Host "===== 10. ENERGY SERVER ====="
$esrv = Get-Service -Name ESRV_SVC_QUEENCREEK -ErrorAction SilentlyContinue
if ($esrv) { Write-Host "ESRV: $($esrv.Status) / $($esrv.StartType)" } else { Write-Host "ESRV: NOT FOUND (fully removed)" }

Write-Host ""
Write-Host "===== 11. E: DRIVE ====="
$edrive = Get-Volume -DriveLetter E -ErrorAction SilentlyContinue
if ($edrive) { Write-Host "E: drive CONNECTED - $([math]::Round($edrive.Size/1GB,1)) GB" } else { Write-Host "E: drive DISCONNECTED" }

Write-Host ""
Write-Host "===== 12. C: DRIVE ====="
$c = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
Write-Host "Free: $([math]::Round($c.FreeSpace/1GB,1)) GB / $([math]::Round($c.Size/1GB,1)) GB"

Write-Host ""
Write-Host "===== 13. WSL ====="
$wsl = Get-Process -Name vmmemWSL -ErrorAction SilentlyContinue
if ($wsl) { Write-Host "WSL running: $([math]::Round($wsl.WorkingSet64/1MB,1)) MB" } else { Write-Host "WSL: STOPPED" }

Write-Host ""
Write-Host "===== 14. HYPER-V Event 167 ====="
$hv167 = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Hyper-V-Hypervisor'; Id=167; StartTime=$bootTime} -MaxEvents 5 -ErrorAction SilentlyContinue
Write-Host "Event 167 since boot: $($hv167.Count) (benign - no crash correlation)"

Write-Host ""
Write-Host "===== 15. STARTUP ITEMS ====="
$runHKLM = Get-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue
$runHKCU = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue
$items = 0
foreach ($p in $runHKLM.PSObject.Properties) { if ($p.Name -notmatch '^PS') { $items++; Write-Host "  HKLM: $($p.Name)" } }
foreach ($p in $runHKCU.PSObject.Properties) { if ($p.Name -notmatch '^PS') { $items++; Write-Host "  HKCU: $($p.Name)" } }
Write-Host "Total: $items"

Write-Host ""
Write-Host "===== 16. HIBERNATION ====="
if (Test-Path C:\hiberfil.sys) { Write-Host "hiberfil.sys EXISTS" } else { Write-Host "hiberfil.sys GONE" }

Write-Host ""
Write-Host "===== 17. WUDFRd ERRORS ====="
$wudf = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-PnP'; Id=219; StartTime=$bootTime} -MaxEvents 20 -ErrorAction SilentlyContinue | Where-Object { $PSItem.Message -match 'WUDFRd' }
Write-Host "WUDFRd load failures: $($wudf.Count)"

Write-Host ""
Write-Host "===== 18. PROCESSOR THROTTLING ====="
$throttle = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Processor-Power'; Id=37; StartTime=$bootTime} -MaxEvents 10 -ErrorAction SilentlyContinue
Write-Host "Throttle events: $($throttle.Count)"

Write-Host ""
Write-Host "===== 19. TOP PROCESSES ====="
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name, @{N='WS_MB';E={[math]::Round($PSItem.WorkingSet64/1MB,1)}}, @{N='Priv_MB';E={[math]::Round($PSItem.PrivateMemorySize64/1MB,1)}} | Format-Table -AutoSize

Write-Host ""
Write-Host "===== 20. PROCESS/THREAD/HANDLE COUNT ====="
$procs = Get-Process
$totalThreads = 0; foreach ($p in $procs) { $totalThreads += ($p.Threads | Measure-Object).Count }
$totalHandles = 0; foreach ($p in $procs) { $totalHandles += $p.HandleCount }
Write-Host "Processes: $($procs.Count)"
Write-Host "Threads: $totalThreads"
Write-Host "Handles: $totalHandles"

Write-Host ""
Write-Host "============================================"
Write-Host "  HEALTH SCORE"
Write-Host "============================================"
$score = 100
$issues = @()
if ($recent41.Count -gt 0) { $score -= 30; $issues += "Recent Event 41 crashes" }
if ($np -gt 800) { $score -= 20; $issues += "Nonpaged pool critically high ($np MB)" }
elseif ($np -gt 700) { $score -= 10; $issues += "Nonpaged pool elevated ($np MB)" }
if ($errors.Count -gt 5) { $score -= 10; $issues += "$($errors.Count) errors since boot" }
if ($kl -gt 0) { $score -= 20; $issues += "Kaspersky drivers still loaded" }
if ($aceDrv -gt 0) { $score -= 20; $issues += "ACE drivers still loaded" }
if ($huaweiRunning -gt 0) { $score -= 20; $issues += "Huawei services running" }
if ($wudf.Count -gt 0) { $score -= 5; $issues += "WUDFRd load failures ($($wudf.Count))" }
if ($throttle.Count -gt 5) { $score -= 5; $issues += "Frequent CPU throttling ($($throttle.Count))" }
if ($freeMem -lt 1) { $score -= 10; $issues += "Critically low memory" }
elseif ($freeMem -lt 2) { $score -= 5; $issues += "Low memory" }

Write-Host "Score: $score/100"
if ($issues.Count -gt 0) {
    Write-Host ""
    Write-Host "Issues:"
    foreach ($i in $issues) { Write-Host "  - $i" }
} else {
    Write-Host "No issues found"
}

if ($score -ge 90) { Write-Host "VERDICT: HEALTHY" }
elseif ($score -ge 70) { Write-Host "VERDICT: MINOR ISSUES" }
else { Write-Host "VERDICT: NEEDS ATTENTION" }

Read-Host
