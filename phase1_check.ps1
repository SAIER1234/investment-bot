
Write-Host "============================================"
Write-Host "  PHASE 1: CURRENT STATUS"
Write-Host "============================================"

Write-Host ""
Write-Host "--- 1. NEW Event 41 since ACE uninstall ---"
$aceUninstallTime = Get-Date "2026-07-25 22:51:00"
$new41 = Get-WinEvent -FilterHashtable @{LogName='System'; Id=41; StartTime=$aceUninstallTime} -MaxEvents 5 -ErrorAction SilentlyContinue
Write-Host "Event 41 since ACE removed: $($new41.Count)"
if ($new41.Count -gt 0) {
    foreach ($e in $new41) { Write-Host "  CRASH: $($e.TimeCreated)" }
} else { Write-Host "  NO crashes since ACE removal!" }

Write-Host ""
Write-Host "--- 2. System uptime and stability ---"
$uptime = [math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours, 1)
Write-Host "Uptime: $uptime hours"
$recentErrors = Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=(Get-Date).AddHours(-2)} -MaxEvents 50 -ErrorAction SilentlyContinue
Write-Host "Errors in last 2 hours: $($recentErrors.Count)"

Write-Host ""
Write-Host "--- 3. E: DRIVE INVESTIGATION ---"
Write-Host "E: drive status:"
$edisk = Get-PhysicalDisk | Where-Object { $PSItem.FriendlyName -match 'Passport' }
if ($edisk) {
    Write-Host "  Connected: $($edisk.FriendlyName)"
    Write-Host "  Health: $($edisk.HealthStatus)"
    Write-Host "  BusType: $($edisk.BusType)"

    # Check for recent disk errors for Harddisk1
    $diskErrors = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='disk'; StartTime=(Get-Date).AddHours(-24)} -MaxEvents 20 -ErrorAction SilentlyContinue
    $hdd1Errors = $diskErrors | Where-Object { $PSItem.Message -match 'Harddisk1' }
    Write-Host "  Disk errors (24h): $($hdd1Errors.Count)"

    # Check USB selective suspend
    Write-Host ""
    Write-Host "  USB power settings:"
    powercfg /query SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 2>&1 | Select-String 'USB|Selective|Suspend|selective|suspend' -Context 1,0
}

Write-Host ""
Write-Host "--- 4. Current nonpaged pool ---"
$mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
Write-Host "Nonpaged: $([math]::Round($mem.PoolNonpagedBytes/1MB,1)) MB"

Write-Host ""
Write-Host "--- 5. Memory ---"
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "Free: $([math]::Round($os.FreePhysicalMemory/1MB,1)) GB"

Write-Host ""
Write-Host "--- 6. Remnants (ACE, SbieDrv) ---"
$aceReg = Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services" -ErrorAction SilentlyContinue | Where-Object { $PSItem.PSChildName -match '^ace-|^ACE-' }
Write-Host "ACE registry keys: $($aceReg.Count)"
$sb = Get-Service -Name SbieDrv -ErrorAction SilentlyContinue
if ($sb) { Write-Host "SbieDrv: $($sb.Status) / $($sb.StartType)" }

Write-Host ""
Write-Host "--- 7. WUDFRd errors (24h) ---"
$wudfErrors = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-PnP'; Id=219; StartTime=(Get-Date).AddHours(-24)} -MaxEvents 10 -ErrorAction SilentlyContinue | Where-Object { $PSItem.Message -match 'WUDFRd' }
Write-Host "WUDFRd load failures (24h): $($wudfErrors.Count)"

Write-Host ""
Write-Host "--- 8. Processor throttling (24h) ---"
$throttle = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Processor-Power'; Id=37; StartTime=(Get-Date).AddHours(-24)} -MaxEvents 10 -ErrorAction SilentlyContinue
Write-Host "Processor throttle events (24h): $($throttle.Count)"

Write-Host ""
Write-Host "--- THEORY TEST ---"
Write-Host "External USB HDD theory: drive spins down -> Windows tries"
Write-Host "background access -> USB wake-up delay -> I/O timeout -> freeze"
Write-Host ""
Write-Host "Test: We'll temporarily remove E: drive letter and see if"
Write-Host "freezes stop. Data is safe - just unmount, not format."

Read-Host
