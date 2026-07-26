
Write-Host "============================================"
Write-Host "  DEEP DIAGNOSTIC - 3 REMAINING ISSUES"
Write-Host "============================================"

Write-Host ""
Write-Host "--- ISSUE 1: NONPAGED POOL GROWTH ---"
Write-Host "Poolmon is not available. Trying alternative approach..."
Write-Host ""

Write-Host "Checking pool tags via xperf or alternative..."
$pool = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
Write-Host "Nonpaged Pool Bytes: $($pool.PoolNonpagedBytes)"
Write-Host "Nonpaged Pool Allocations: $($pool.PoolNonpagedAllocs)"

Write-Host ""
Write-Host "Top drivers by pool usage from registry:"
$drivers = Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services" -ErrorAction SilentlyContinue | Where-Object {
    $PSItem.PSChildName -notmatch '^\.' -and (Test-Path "$($PSItem.PSPath)\Parameters")
} | ForEach-Object { $PSItem.PSChildName }
Write-Host "Total driver services found: $($drivers.Count)"

Write-Host ""
Write-Host "Checking largest pool allocations by looking at pool tags..."
# Try to get pool tag info from kernel debugger or ETW
try {
    $poolData = Get-CimInstance -Namespace root/wmi -ClassName PoolMon -ErrorAction Stop
    Write-Host "PoolMon data available!"
    $poolData | Sort-Object NonPagedUsed -Descending | Select-Object -First 10 Tag, NonPagedUsed, PagedUsed | Format-Table -AutoSize
} catch {
    Write-Host "PoolMon WMI class not available"
}

Write-Host ""
Write-Host "--- ISSUE 2: PROCESSOR THROTTLING (Event 37) ---"
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$throttleEvents = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Processor-Power'; Id=37; StartTime=$bootTime} -MaxEvents 5 -ErrorAction SilentlyContinue
foreach ($e in $throttleEvents) {
    if ($e.Message -match 'processor (\d+)' -and $e.Message -match '(\d+) seconds') {
        Write-Host "Core(s) throttled: $($Matches[1]) for $($Matches[2]) seconds"
    }
    if ($e.Message -match '受限') {
        Write-Host "Reason: thermal/power limit"
    }
}

Write-Host ""
Write-Host "Current power plan:"
powercfg /getactivescheme
Write-Host ""
Write-Host "Processor power settings:"
powercfg /query SCHEME_CURRENT SUB_PROCESSOR 2>&1 | Select-String 'maximum|minimum|throttle|Performance|frequency|policy' -Context 0,0

Write-Host ""
Write-Host "--- ISSUE 3: WUDFRd LOAD FAILURES ---"
$pnpEvents = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-PnP'; Id=219; StartTime=$bootTime} -MaxEvents 10 -ErrorAction SilentlyContinue
foreach ($e in $pnpEvents) {
    if ($e.Message -match 'Driver\\WUDFRd') {
        Write-Host "WUDFRd load failure!"
        if ($e.Message -match 'ACPI\\\\(SIL\w+)') { Write-Host "  Device: $($Matches[1]) (touchscreen/sensor)" }
        if ($e.Message -match 'STATUS_(\w+)') { Write-Host "  Error: STATUS_$($Matches[1])" }
    }
}

Write-Host ""
Write-Host "--- ISSUE 4: Check for any NEW problems ---"
Write-Host "Kaspersky drivers loaded:"
$klDrivers = Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -like 'kl*' -and $PSItem.State -eq 'Running' }
Write-Host "  Count: $($klDrivers.Count)"

Write-Host ""
Write-Host "Check Windows Update install history for firmware:"
$wuHistory = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WindowsUpdateClient'} -MaxEvents 20 -ErrorAction SilentlyContinue | Where-Object { $PSItem.Id -in @(19,43,44) }
foreach ($e in $wuHistory) {
    if ($e.Message -match 'HUAWEI|Firmware|固件|firmware') {
        Write-Host "$($e.TimeCreated) - Id=$($e.Id) - Firmware update event found"
    }
}
Write-Host "(If no firmware events, it may have installed silently)"

Write-Host ""
Write-Host "============================================"
Read-Host
