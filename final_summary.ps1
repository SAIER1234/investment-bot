
Write-Host "============================================"
Write-Host "  FINAL STATUS BEFORE E: DRIVE TEST"
Write-Host "============================================"

Write-Host ""
Write-Host "=== ALL FIXES APPLIED ==="
$fixes = @(
    @{Name="Huawei 10 services"; Status="Disabled"},
    @{Name="Kaspersky 16 drivers"; Status="Uninstalled"},
    @{Name="ACE 8 drivers"; Status="Uninstalled"},
    @{Name="Energy Server"; Status="Stopped/Manual"},
    @{Name="USBPcap driver"; Status="Disabled"},
    @{Name="PRI-Driver orphan"; Status="Disabled"},
    @{Name="TxQBService orphan"; Status="Disabled"},
    @{Name="Hyper-V Event 167"; Status="WHP enabled"},
    @{Name="USB selective suspend"; Status="DISABLED"},
    @{Name="Disk sleep timeout"; Status="NEVER"},
    @{Name="Hibernation"; Status="REMOVED"},
    @{Name="C: drive cleanup"; Status="39GB free"},
    @{Name="Startup items"; Status="6 -> 2"},
    @{Name="WSL memory"; Status="3GB + pageReporting"},
    @{Name="ace-game-0 remnant"; Status="Disabled"},
    @{Name="SbieDrv"; Status="Disabled (reboot to unload)"}
)
foreach ($f in $fixes) {
    Write-Host ("  $($f.Name).PadRight(28) $($f.Status)")
}

Write-Host ""
Write-Host "=== REMAINING CONCERNS ==="
Write-Host "  1. WUDFRd load failures (touchscreen/sensor power issue)"
Write-Host "     - BIOS/firmware update recommended"
Write-Host "  2. Processor throttling events"
Write-Host "     - Check thermal paste / fan / ventilation"
Write-Host "  3. Nonpaged pool ~695 MB"
Write-Host "     - Slightly elevated, monitor over time"
Write-Host "  4. E: drive external HDD (THEORY)"
Write-Host "     - UNPLUG FOR 24 HOURS TO TEST"

Write-Host ""
Write-Host "=== ACTION ITEMS FOR YOU ==="
Write-Host "  1. UNPLUG E: drive now"
Write-Host "  2. Memory diagnostic: press Win+R, type mdsched.exe"
Write-Host "     Select 'Restart now and check for problems'"
Write-Host "  3. Use computer normally for 24 hours"
Write-Host "  4. If freezes stop -> E: drive was the cause"
Write-Host "     Fix: new USB cable / different USB port / powered hub"
Write-Host "  5. If freezes continue -> hardware issue"
Write-Host "     RAM / SSD / motherboard - needs physical diagnosis"

Write-Host ""
Write-Host "============================================"
Read-Host
