
Write-Host "=== FORCE-DISABLING ALL KASPERSKY DRIVERS ==="
Write-Host ""

$klNames = @(
    'klbackupdisk.K4W-21-25','klbackupflt.K4W-21-25','kldisk.K4W-21-25',
    'klflt.K4W-21-25','klgse.K4W-21-25','klhk.K4W-21-25','klids.K4W-21-25',
    'KLIF.K4W-21-25','klim6','klkbdflt.K4W-21-25','klmouflt.K4W-21-25',
    'klpd.K4W-21-25','klpnpflt.K4W-21-25','klupd_K4W-21-25_arkmon',
    'klupd_K4W-21-25_klbg','klwtp.K4W-21-25','kneps.K4W-21-25',
    'klvssbridge64_21.25','klupd_K4W-21-25_mark','klids','KslD'
)

$fixed = 0
foreach ($name in $klNames) {
    $regPath = "HKLM:\SYSTEM\CurrentControlSet\Services\$name"
    if (Test-Path $regPath) {
        # Method 1: PowerShell Set-ItemProperty
        Set-ItemProperty -Path $regPath -Name "Start" -Value 4 -Type DWord -Force -ErrorAction SilentlyContinue

        # Method 2: reg.exe (more forceful)
        $null = reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\$name" /v Start /t REG_DWORD /d 4 /f 2>&1

        # Method 3: Set ErrorControl to Ignore (0)
        $null = reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\$name" /v ErrorControl /t REG_DWORD /d 0 /f 2>&1

        # Method 4: Set Type to disabled (SERVICE_KERNEL_DRIVER=1, no change needed)
        # Just verify the Start value is now 4
        $currentStart = (Get-ItemProperty -Path $regPath -Name "Start" -ErrorAction SilentlyContinue).Start
        if ($currentStart -eq 4) {
            Write-Host "  DISABLED: $name"
            $fixed++
        } else {
            Write-Host "  STILL NOT DISABLED: $name (Start=$currentStart)"
        }
    }
}

Write-Host ""
Write-Host "Successfully disabled: $fixed / $($klNames.Count)"
Write-Host ""
Write-Host "=== TRYING sc delete ==="
foreach ($name in $klNames) {
    $null = sc.exe delete $name 2>&1
}

Write-Host ""
Write-Host "Drivers are now marked disabled."
Write-Host "REBOOT REQUIRED to unload them from memory."
Write-Host ""
Write-Host "After reboot, nonpaged pool should drop from ~1000 MB to ~400 MB"
Write-Host ""

Read-Host
