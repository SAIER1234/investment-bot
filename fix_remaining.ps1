
Write-Host "=== Fix 1: SbieDrv running despite being disabled ==="
$svc = Get-Service -Name SbieDrv -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host "Status: $($svc.Status) / $($svc.StartType)"
    sc.exe stop SbieDrv 2>&1
    sc.exe config SbieDrv start= disabled 2>&1
    Write-Host "Stopped and re-disabled"
} else {
    Write-Host "SbieDrv not found as service"
}

Write-Host ""
Write-Host "=== Fix 2: Check esrv process ==="
$esrvProcs = Get-Process -Name esrv* -ErrorAction SilentlyContinue
if ($esrvProcs) {
    foreach ($p in $esrvProcs) {
        Write-Host "Process: $($p.Name) PID: $($p.Id)"
        Write-Host "Path: $($p.Path)"
        Write-Host "Mem: $([math]::Round($p.WorkingSet64/1MB,1)) MB"
    }
}

Write-Host ""
Write-Host "=== Fix 3: Check page file configuration ==="
Get-CimInstance Win32_PageFileSetting | Select-Object Name, InitialSize, MaximumSize | Format-Table -AutoSize
$pf = Get-CimInstance Win32_ComputerSystem
Write-Host "AutomaticManagedPagefile: $($pf.AutomaticManagedPagefile)"

Write-Host ""
Write-Host "=== Fix 4: Check WUDFRd status ==="
if (Test-Path "C:\Windows\System32\drivers\WUDFRd.sys") {
    $wudf = Get-Item "C:\Windows\System32\drivers\WUDFRd.sys" -Force
    Write-Host "WUDFRd.sys exists - Size: $($wudf.Length) bytes, Modified: $($wudf.LastWriteTime)"
} else {
    Write-Host "WUDFRd.sys MISSING!"
}

Write-Host ""
Write-Host "=== Fix 5: Processor throttling check ==="
Write-Host "Power plan:"
powercfg /getactivescheme

Write-Host ""
Write-Host "=== Fix 6: DISM final result ==="
$dism = Get-Process -Name dism -ErrorAction SilentlyContinue
if ($dism) { Write-Host "DISM still running..." } else { Write-Host "DISM completed" }

Write-Host ""
Write-Host "=== Fix 7: SFC check ==="
if (Test-Path "C:\Windows\Logs\CBS\CBS.log") {
    $lastLines = Get-Content "C:\Windows\Logs\CBS\CBS.log" -Tail 10
    foreach ($line in $lastLines) {
        if ($line -match 'repair|corrupt|error') { Write-Host $line }
    }
} else {
    Write-Host "CBS.log not found"
}

Read-Host
