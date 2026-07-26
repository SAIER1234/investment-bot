
Write-Host "============================================"
Write-Host "  FINAL COMPREHENSIVE SYSTEM SWEEP"
Write-Host "============================================"

Write-Host ""
Write-Host "--- 1. MEMORY ---"
$os = Get-CimInstance Win32_OperatingSystem
$freeMem = [math]::Round($os.FreePhysicalMemory/1MB, 1)
$totalMem = [math]::Round($os.TotalVisibleMemorySize/1MB, 1)
$freePct = [math]::Round($os.FreePhysicalMemory/$os.TotalVisibleMemorySize*100, 1)
Write-Host "Free: $freeMem GB / $totalMem GB ($freePct%)"
$mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
$np = [math]::Round($mem.PoolNonpagedBytes/1MB, 1)
$pp = [math]::Round($mem.PoolPagedBytes/1MB, 1)
Write-Host "Nonpaged Pool: $np MB"
Write-Host "Paged Pool: $pp MB"
if ($np -gt 800) { Write-Host "! WARNING: Nonpaged pool elevated" }

Write-Host ""
Write-Host "--- 2. PROCESSES ---"
$procs = Get-Process
Write-Host "Total processes: $($procs.Count)"
$totalThreads = 0; foreach ($p in $procs) { $totalThreads += ($p.Threads | Measure-Object).Count }
Write-Host "Total threads: $totalThreads"
$totalHandles = 0; foreach ($p in $procs) { $totalHandles += $p.HandleCount }
Write-Host "Total handles: $totalHandles"

Write-Host ""
Write-Host "--- 3. TOP MEMORY CONSUMERS (WorkingSet) ---"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name, @{N='WS_MB';E={[math]::Round($PSItem.WorkingSet64/1MB,1)}}, @{N='Priv_MB';E={[math]::Round($PSItem.PrivateMemorySize64/1MB,1)}} | Format-Table -AutoSize

Write-Host ""
Write-Host "--- 4. TOP CPU CONSUMERS ---"
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, @{N='CPU_sec';E={[math]::Round($PSItem.CPU,1)}} | Format-Table -AutoSize

Write-Host ""
Write-Host "--- 5. VERIFY ALL PROBLEM SERVICES STILL DEAD ---"
$checkSvc = @('HiConnectivityService','HwPCCoreService','HwDistributedMainService','HWSyncService','MBAMainService','ShellHWDetection','ESRV_SVC_QUEENCREEK','SystemUsageReportSvc_QUEENCREEK','HuaweiHiSuiteService64.exe')
$problems = 0
foreach ($name in $checkSvc) {
    $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne 'Stopped') {
        Write-Host "! PROBLEM: $name is $($svc.Status)"
        $problems++
    }
}
Write-Host "Problem services running: $problems"

Write-Host ""
Write-Host "--- 6. PROBLEM PROCESSES ---"
$problemProcs = @('esrv','HiConnectivityService','HwPCCoreService')
foreach ($name in $problemProcs) {
    $p = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($p) { Write-Host "! RUNNING: $name ($([math]::Round($p.WorkingSet64/1MB,1)) MB)" }
    else { Write-Host "  OK: $name not running" }
}

Write-Host ""
Write-Host "--- 7. ERROR EVENTS SINCE BOOT ---"
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$uptime = [math]::Round(((Get-Date) - $bootTime).TotalHours, 1)
Write-Host "Uptime: $uptime hours"
$errors = Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=$bootTime} -MaxEvents 50 -ErrorAction SilentlyContinue
Write-Host "Critical/Error events: $($errors.Count)"
if ($errors.Count -gt 0) {
    $errors | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 10 Count, Name | Format-Table -AutoSize
}

Write-Host ""
Write-Host "--- 8. WARNINGS SINCE BOOT ---"
$warnings = Get-WinEvent -FilterHashtable @{LogName='System'; Level=3; StartTime=$bootTime} -MaxEvents 50 -ErrorAction SilentlyContinue
Write-Host "Warning events: $($warnings.Count)"
if ($warnings.Count -gt 0) {
    $warnings | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 10 Count, Name | Format-Table -AutoSize
}

Write-Host ""
Write-Host "--- 9. DISK HEALTH ---"
Get-PhysicalDisk | Select-Object FriendlyName, MediaType, OperationalStatus, HealthStatus, @{N='SizeGB';E={[math]::Round($PSItem.Size/1GB,1)}} | Format-Table -AutoSize

Write-Host ""
Write-Host "--- 10. C: DRIVE ---"
$c = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
Write-Host "Free: $([math]::Round($c.FreeSpace/1GB,1)) GB / $([math]::Round($c.Size/1GB,1)) GB ($([math]::Round(($c.Size-$c.FreeSpace)/$c.Size*100,1))% used)"

Write-Host ""
Write-Host "--- 11. WSL STATUS ---"
$wsl = Get-Process -Name vmmemWSL -ErrorAction SilentlyContinue
if ($wsl) { Write-Host "WSL running: $([math]::Round($wsl.WorkingSet64/1MB,1)) MB" }
else { Write-Host "WSL: STOPPED (0 MB)" }

Write-Host ""
Write-Host "--- 12. WINDOWS DEFENDER ---"
$def = Get-Process -Name MsMpEng -ErrorAction SilentlyContinue
if ($def) { Write-Host "Defender: $([math]::Round($def.WorkingSet64/1MB,1)) MB" }

Write-Host ""
Write-Host "--- 13. AUTOSTART SERVICES (check for regressions) ---"
$autoServices = Get-Service | Where-Object { $PSItem.StartType -eq 'Automatic' -and $PSItem.Status -eq 'Running' } | Measure-Object
Write-Host "Running auto-start services: $($autoServices.Count)"

Read-Host
