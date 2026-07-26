
Write-Host "=== DISABLING 16 KASPERSKY ORPHAN KERNEL DRIVERS ==="
Write-Host ""

$klDrivers = Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -like 'kl*' -or $PSItem.Name -like 'klim6' -or $PSItem.Name -like 'kneps*' -or $PSItem.Name -like 'KslD' } | Where-Object { $PSItem.State -eq 'Running' }
Write-Host "Found $($klDrivers.Count) Kaspersky kernel drivers running"

$fixed = 0
foreach ($drv in $klDrivers) {
    $name = $drv.Name
    try {
        # Stop the driver
        sc.exe stop $name 2>&1 | Out-Null

        # Set to Disabled (Start=4)
        $regPath = "HKLM:\SYSTEM\CurrentControlSet\Services\$name"
        if (Test-Path $regPath) {
            Set-ItemProperty -Path $regPath -Name "Start" -Value 4 -Type DWord -Force
        }

        Write-Host "  DISABLED: $name"
        $fixed++
    } catch {
        Write-Host "  FAILED: $name - $_"
    }
}

Write-Host ""
Write-Host "Disabled: $fixed / $($klDrivers.Count)"
Write-Host ""
Write-Host "NOTE: These will be fully disabled after reboot."
Write-Host "      Running drivers may still hold pool allocations until reboot."

Write-Host ""
Write-Host "=== Check nonpaged pool after disabling ==="
$mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
$np = [math]::Round($mem.PoolNonpagedBytes/1MB, 1)
Write-Host "Nonpaged Pool: $np MB"

Read-Host
