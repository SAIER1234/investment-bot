
Write-Host "=== Final cleanup ==="

Write-Host ""
Write-Host "--- Fix SbieDrv ---"
sc.exe config SbieDrv start= disabled 2>&1
reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\SbieDrv" /v Start /t REG_DWORD /d 4 /f 2>&1
$svc = Get-Service -Name SbieDrv -ErrorAction SilentlyContinue
if ($svc) {
    $start = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\SbieDrv").Start
    Write-Host "SbieDrv Start=$start (4=Disabled)"
    Write-Host "Will not load on next boot"
}

Write-Host ""
Write-Host "--- Fix Hyper-V Event 167 ---"
bcdedit /set hypervisorlaunchtype auto 2>&1
Write-Host "BCD updated"

Write-Host ""
Write-Host "Done. SbieDrv disabled for next boot."
Write-Host "Hypervisor mitigations: reboot to apply."
Read-Host
