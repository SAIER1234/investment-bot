
Write-Host "=== PHASE 1: Killing all Huawei user processes ==="
$huaweiProcs = @('HiConnectivityService', 'HwMdcCenter', 'HwMdcUI', 'HwPCCoreService')
foreach ($name in $huaweiProcs) {
    $proc = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($proc) {
        taskkill /f /im "$name.exe" 2>$null
        Write-Host "Killed $name"
    }
}
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "=== PHASE 2: Disabling service via REG ==="
# Use reg.exe directly (more reliable for protected services)
cmd /c 'reg add "HKLM\SYSTEM\CurrentControlSet\Services\HiConnectivityService" /v Start /t REG_DWORD /d 4 /f' 2>&1
cmd /c 'reg add "HKLM\SYSTEM\CurrentControlSet\Services\HwPCCoreService" /v Start /t REG_DWORD /d 4 /f' 2>&1
cmd /c 'reg add "HKLM\SYSTEM\CurrentControlSet\Services\HW_OSDServer" /v Start /t REG_DWORD /d 3 /f' 2>&1
cmd /c 'reg add "HKLM\SYSTEM\CurrentControlSet\Services\HWVEAudioService" /v Start /t REG_DWORD /d 3 /f' 2>&1
cmd /c 'reg add "HKLM\SYSTEM\CurrentControlSet\Services\LCD_Service" /v Start /t REG_DWORD /d 3 /f' 2>&1

# Also disable recovery
cmd /c 'reg add "HKLM\SYSTEM\CurrentControlSet\Services\HiConnectivityService" /v FailureActions /t REG_BINARY /d 00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000 /f' 2>&1

Write-Host ""
Write-Host "=== PHASE 3: Stop all remaining Huawei services ==="
sc.exe stop HiConnectivityService 2>&1
sc.exe stop HwPCCoreService 2>&1
sc.exe stop HW_OSDServer 2>&1
sc.exe stop HWVEAudioService 2>&1
sc.exe stop LCD_Service 2>&1

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "=== FINAL STATUS ==="
@('HiConnectivityService','HwPCCoreService','HW_OSDServer','HWVEAudioService','LCD_Service') | ForEach-Object {
    $svc = Get-Service -Name $_ -ErrorAction SilentlyContinue
    if ($svc) { Write-Host "$_ : $($svc.Status) / $($svc.StartType)" }
}

$proc = Get-Process -Name 'HiConnectivityService','HwPCCoreService' -ErrorAction SilentlyContinue
if ($proc) { Write-Host "WARNING: Some processes still alive!" } else { Write-Host "All target processes DEAD" }

$os = Get-CimInstance Win32_OperatingSystem
Write-Host ""
Write-Host "Free Memory: $([math]::Round($os.FreePhysicalMemory/1MB,1)) GB"

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
