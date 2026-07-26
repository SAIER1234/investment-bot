
Write-Host "============================================"
Write-Host "  POST-REBOOT VERIFICATION"
Write-Host "============================================"

Write-Host ""
Write-Host "--- 1. HYPER-V EVENT 167 (the smoking gun) ---"
$hv167 = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Hyper-V-Hypervisor'; Id=167} -MaxEvents 20 -ErrorAction SilentlyContinue
$recent167 = $hv167 | Where-Object { $PSItem.TimeCreated -gt (Get-Date).AddHours(-1) }
Write-Host "Event 167 in last hour: $($recent167.Count)"
if ($recent167.Count -eq 0) { Write-Host "  CLEAN! No hypervisor crashes since reboot" }
else { Write-Host "  STILL OCCURRING!"; foreach ($e in $recent167) { Write-Host "  $($e.TimeCreated)" } }

Write-Host ""
Write-Host "--- 2. EVENT 41 (forced shutdown) ---"
$ev41 = Get-WinEvent -FilterHashtable @{LogName='System'; Id=41; StartTime=(Get-Date).AddDays(-1)} -MaxEvents 5 -ErrorAction SilentlyContinue
Write-Host "Event 41 in last 24h: $($ev41.Count)"
if ($ev41.Count -eq 0) { Write-Host "  CLEAN!" }

Write-Host ""
Write-Host "--- 3. HYPERVISOR CONFIG ---"
$vmp = (Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform).State
$whp = (Get-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform).State
Write-Host "VirtualMachinePlatform: $vmp"
Write-Host "HypervisorPlatform: $whp"
if ($whp -eq 'Enabled') { Write-Host "  WHP ACTIVE - VMware + WSL2 can coexist" }

Write-Host ""
Write-Host "--- 4. MEMORY ---"
$os = Get-CimInstance Win32_OperatingSystem
$freeMem = [math]::Round($os.FreePhysicalMemory/1MB, 1)
Write-Host "Free: $freeMem GB"
$mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
$np = [math]::Round($mem.PoolNonpagedBytes/1MB, 1)
Write-Host "Nonpaged Pool: $np MB"
Write-Host ("Status: " + $(if ($np -lt 400) { "EXCELLENT" } elseif ($np -lt 600) { "GOOD" } else { "ELEVATED - monitor" }))

Write-Host ""
Write-Host "--- 5. PROBLEM SERVICES ---"
$checkSvc = @('HiConnectivityService','HwPCCoreService','HwDistributedMainService','HWSyncService','MBAMainService','ESRV_SVC_QUEENCREEK','SbieDrv')
$running = 0
foreach ($n in $checkSvc) {
    $s = Get-Service -Name $n -ErrorAction SilentlyContinue
    if ($s -and $s.Status -ne 'Stopped') { Write-Host "! $n is $($s.Status)"; $running++ }
}
Write-Host "Problem services running: $running"

Write-Host ""
Write-Host "--- 6. KASPERSKY DRIVERS ---"
$kl = (Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -like 'kl*' -and $PSItem.State -eq 'Running' } | Measure-Object).Count
Write-Host "Kaspersky kernel drivers: $kl"

Write-Host ""
Write-Host "--- 7. HC MON / USBPcap ---"
$hcmonCount = (Get-EventLog -LogName System -Source hcmon -After (Get-Date).AddDays(-1) -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "hcmon events in last 24h: $hcmonCount"

Write-Host ""
Write-Host "--- 8. C: DRIVE ---"
$c = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
Write-Host "Free: $([math]::Round($c.FreeSpace/1GB,1)) GB"
Write-Host "Hiberfil.sys: $(if (Test-Path C:\hiberfil.sys) { 'STILL EXISTS' } else { 'GONE' })"

Write-Host ""
Write-Host "--- 9. WSL ---"
$wslMem = Get-Process -Name vmmemWSL -ErrorAction SilentlyContinue
if ($wslMem) { Write-Host "WSL running: $([math]::Round($wslMem.WorkingSet64/1MB,1)) MB" }
else { Write-Host "WSL: STOPPED" }

Write-Host ""
Write-Host "--- 10. ERRORS SINCE BOOT ---"
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$errs = Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=$bootTime} -MaxEvents 20 -ErrorAction SilentlyContinue
Write-Host "Errors since boot: $($errs.Count)"
if ($errs.Count -gt 0) {
    $errs | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 5 Count, Name | Format-Table -AutoSize
}

Write-Host ""
Write-Host "============================================"
Write-Host "  VERDICT"
Write-Host "============================================"
$issues = 0
if ($recent167.Count -gt 0) { $issues++; Write-Host "! Hyper-V Event 167 still active" }
if ($np -gt 600) { $issues++; Write-Host "! Nonpaged pool elevated: $np MB" }
if ($running -gt 0) { $issues++; Write-Host "! Problem services running" }
if ($kl -gt 0) { $issues++; Write-Host "! Kaspersky drivers still loaded" }
if ($ev41.Count -gt 0) { $issues++; Write-Host "! Recent forced shutdown detected" }
if ($issues -eq 0) { Write-Host "ALL CHECKS PASSED - SYSTEM IS CLEAN" }

Read-Host
