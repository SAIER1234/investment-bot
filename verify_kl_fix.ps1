
Write-Host "=== Kaspersky drivers after fix ==="
$klAll = Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services" -ErrorAction SilentlyContinue | Where-Object { $PSItem.PSChildName -match '^kl|^klim|^kneps|^KslD' }
$disabled = 0
$stillAlive = @()
foreach ($entry in $klAll) {
    $name = $entry.PSChildName
    $start = (Get-ItemProperty -Path $entry.PSPath -Name "Start" -ErrorAction SilentlyContinue).Start
    if ($start -eq 4) { $disabled++ }
    $drvStatus = Get-CimInstance Win32_SystemDriver -Filter "Name='$name'" -ErrorAction SilentlyContinue
    if ($drvStatus -and $drvStatus.State -eq 'Running') {
        $stillAlive += "$name (running)"
    }
}
Write-Host "Kaspersky services in registry: $($klAll.Count)"
Write-Host "Set to Disabled (Start=4): $disabled"
Write-Host "Still running (until reboot): $($stillAlive.Count)"
if ($stillAlive.Count -gt 0) {
    foreach ($s in $stillAlive) { Write-Host "  - $s" }
}

Write-Host ""
Write-Host "=== Nonpaged pool ==="
$mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
$np = [math]::Round($mem.PoolNonpagedBytes/1MB, 1)
Write-Host "$np MB"

Write-Host ""
Write-Host "=== Free memory ==="
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "$([math]::Round($os.FreePhysicalMemory/1MB,1)) GB"
Read-Host
