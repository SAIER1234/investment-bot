Write-Host "============================================"
Write-Host "  POST-REBOOT VERIFICATION"
Write-Host "============================================"

Write-Host ""
Write-Host "=== 1. Huawei Services ==="
$huaweiSvcs = @('HiConnectivityService','HwPCCoreService','HwDistributedMainService','HWSyncService','MBAMainService','ShellHWDetection','HW_OSDServer','HWVEAudioService','LCD_Service','HuaweiHiSuiteService64.exe')
foreach ($name in $huaweiSvcs) {
    $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($svc) {
        $icon = if ($svc.Status -eq 'Stopped') { 'OK' } else { 'RUNNING!' }
        Write-Host ("  $icon $($name.PadRight(32)) $($svc.Status.ToString().PadRight(10)) $($svc.StartType)")
    } else {
        Write-Host ("  -- $($name.PadRight(32)) NOT FOUND")
    }
}

Write-Host ""
Write-Host "=== 2. Energy Server Service ==="
$esrv = Get-Service -Name ESRV_SVC_QUEENCREEK -ErrorAction SilentlyContinue
if ($esrv) {
    $icon = if ($esrv.Status -eq 'Stopped') { 'OK' } else { 'RUNNING!' }
    Write-Host ("  $icon ESRV_SVC_QUEENCREEK: $($esrv.Status) / $($esrv.StartType)")
}

Write-Host ""
Write-Host "=== 3. USBPcap Driver ==="
$usbStart = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\USBPcap" -ErrorAction SilentlyContinue).Start
Write-Host ("  USBPcap Start value: $usbStart (4=Disabled)")

Write-Host ""
Write-Host "=== 4. PRI-Driver / TxQBService / SbieDrv ==="
$orphanKeys = @('PRI-Driver','TxQBService','SbieDrv')
foreach ($key in $orphanKeys) {
    $path = "HKLM:\SYSTEM\CurrentControlSet\Services\$key"
    if (Test-Path $path) {
        $start = (Get-ItemProperty -Path $path).Start
        Write-Host ("  $key : Start=$start (4=Disabled)")
    } else {
        Write-Host ("  $key : NOT FOUND")
    }
}

Write-Host ""
Write-Host "=== 5. Startup Items ==="
$runHKLM = Get-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue
$props = $runHKLM.PSObject.Properties | Where-Object { $_.Name -notmatch '^PS' }
Write-Host ("  HKLM items: " + ($props | Measure-Object).Count)
foreach ($p in $props) {
    Write-Host ("    - " + $p.Name)
}

Write-Host ""
Write-Host "=== 6. Hibernation ==="
if (Test-Path C:\hiberfil.sys) {
    $size = [math]::Round((Get-Item C:\hiberfil.sys -Force).Length/1GB, 2)
    Write-Host "  hiberfil.sys EXISTS: $size GB"
} else {
    Write-Host "  hiberfil.sys GONE - OK"
}

Write-Host ""
Write-Host "=== 7. C: Drive Space ==="
$drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$free = [math]::Round($drive.FreeSpace/1GB, 1)
$pct = [math]::Round(($drive.Size - $drive.FreeSpace)/$drive.Size*100, 1)
Write-Host ("  Free: $free GB / $([math]::Round($drive.Size/1GB,1)) GB ($pct% used)")

Write-Host ""
Write-Host "=== 8. Memory After Reboot ==="
$os = Get-CimInstance Win32_OperatingSystem
$freeMem = [math]::Round($os.FreePhysicalMemory/1MB, 1)
$totalMem = [math]::Round($os.TotalVisibleMemorySize/1MB, 1)
Write-Host ("  Free: $freeMem GB / $totalMem GB")

Write-Host ""
Write-Host "=== 9. Nonpaged Pool After Reboot ==="
$mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
$np = [math]::Round($mem.PoolNonpagedBytes/1MB, 1)
Write-Host ("  Nonpaged Pool: $np MB (target < 500 MB)")

Write-Host ""
Write-Host "=== 10. Top Driver NP Paged Pool ==="
$drivers = driverquery /v /fo csv 2>$null | ConvertFrom-Csv
$topDrivers = $drivers | Where-Object { $_.'NP Paged(KB)' -and [int]($_.'NP Paged(KB)' -replace ',','') -gt 50000 } | Sort-Object {[int]($_.'NP Paged(KB)' -replace ',','')} -Descending
if ($topDrivers) {
    foreach ($d in $topDrivers) {
        $mb = [math]::Round([int]($d.'NP Paged(KB)' -replace ',','')/1024, 1)
        Write-Host ("  $($d.'Module Name'.PadRight(25)) $mb MB")
    }
} else {
    Write-Host "  No driver above 50 MB NP Pool - GREAT!"
}

Write-Host ""
Write-Host "Press Enter to exit..."
Read-Host
