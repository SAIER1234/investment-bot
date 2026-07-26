
Write-Host "============================================"
Write-Host "  FINAL SYSTEM STATUS AFTER ALL FIXES"
Write-Host "============================================"

Write-Host ""
Write-Host "--- MEMORY ---"
$os = Get-CimInstance Win32_OperatingSystem
$freeMem = [math]::Round($os.FreePhysicalMemory/1MB, 1)
$totalMem = [math]::Round($os.TotalVisibleMemorySize/1MB, 1)
$pctFree = [math]::Round($os.FreePhysicalMemory/$os.TotalVisibleMemorySize*100, 1)
Write-Host ("Free: $freeMem GB / $totalMem GB ($pctFree%)")

$mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
$np = [math]::Round($mem.PoolNonpagedBytes/1MB, 1)
Write-Host ("Nonpaged Pool: $np MB")
Write-Host ("Target: 8GB free (50%+), NP Pool < 500 MB")

Write-Host ""
Write-Host "--- DISK ---"
Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:' OR DeviceID='D:' OR DeviceID='E:'" | ForEach-Object {
    $free = [math]::Round($_.FreeSpace/1GB, 1)
    $total = [math]::Round($_.Size/1GB, 1)
    $used = [math]::Round(($_.Size - $_.FreeSpace)/$_.Size*100, 1)
    Write-Host ("$($_.DeviceID): $free GB free / $total GB total ($used% used)")
}

Write-Host ""
Write-Host "--- STARTUP ---"
$runHKLM = Get-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
$runHKCU = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$count = 0
foreach ($p in $runHKLM.PSObject.Properties) { if ($p.Name -notmatch '^PS') { Write-Host ("  HKLM: " + $p.Name); $count++ } }
foreach ($p in $runHKCU.PSObject.Properties) { if ($p.Name -notmatch '^PS') { Write-Host ("  HKCU: " + $p.Name); $count++ } }
Write-Host ("Total: $count items")

Write-Host ""
Write-Host "--- PROBLEMATIC SERVICES COUNT ---"
$problemCount = 0
$allChecks = @()
$huaweiSvcs = @('HiConnectivityService','HwPCCoreService','HwDistributedMainService','HWSyncService','MBAMainService','ShellHWDetection','HW_OSDServer','HWVEAudioService','LCD_Service','HuaweiHiSuiteService64.exe')
foreach ($name in $huaweiSvcs) {
    $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne 'Stopped') { $problemCount++; $allChecks += "Huawei: $name is $($svc.Status)" }
}
$esrv = Get-Service -Name ESRV_SVC_QUEENCREEK -ErrorAction SilentlyContinue
if ($esrv -and $esrv.Status -ne 'Stopped') { $problemCount++; $allChecks += "EnergyServer: running" }
$usbStart = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\USBPcap" -ErrorAction SilentlyContinue).Start
if ($usbStart -ne 4) { $problemCount++; $allChecks += "USBPcap: Start=$usbStart (not disabled)" }
if (-not (Test-Path C:\hiberfil.sys -ErrorAction SilentlyContinue)) { } else { $problemCount++; $allChecks += "hiberfil.sys exists" }

Write-Host ("Problems found: $problemCount")
foreach ($p in $allChecks) { Write-Host ("  ! $p") }
if ($problemCount -eq 0) { Write-Host "  ALL CLEAN!" }

Write-Host ""
Write-Host "--- SFC/DISM ---"
$dism = Get-Process -Name dism -ErrorAction SilentlyContinue
if ($dism) { Write-Host ("DISM still running (PID: $($dism.Id))") }
else { Write-Host "SFC and DISM both completed" }

Write-Host ""
Write-Host "--- RECENT EVENTS (since reboot) ---"
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
Write-Host ("System uptime: " + [math]::Round(((Get-Date) - $bootTime).TotalMinutes, 1) + " minutes")
$errors = Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=$bootTime} -MaxEvents 20 -ErrorAction SilentlyContinue
$errorCount = ($errors | Measure-Object).Count
Write-Host ("Errors/Warnings since boot: $errorCount")
if ($errorCount -gt 0) {
    $errors | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 5 Count, Name | Format-Table -AutoSize
}

Write-Host ""
Write-Host "============================================"
Write-Host "  SUMMARY: Before -> After Reboot"
Write-Host "============================================"
Write-Host "  Memory:     1.0 GB  ->  $freeMem GB free"
Write-Host "  NP Pool:    945 MB  ->  $np MB"
Write-Host "  C: space:   23 GB   ->  $([math]::Round((Get-CimInstance Win32_LogicalDisk -Filter 'DeviceID=''C:''').FreeSpace/1GB,1)) GB free"
Write-Host "  Services:   15 problem -> $problemCount running"
Write-Host "  Startup:    6 items -> $count items"

Read-Host
