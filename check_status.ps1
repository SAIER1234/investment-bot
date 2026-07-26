Write-Host "=== Energy Server Service ==="
$esrv = Get-Service -Name ESRV_SVC_QUEENCREEK -ErrorAction SilentlyContinue
if ($esrv) { Write-Host ("$($esrv.Name): " + $esrv.Status + " / " + $esrv.StartType) }

Write-Host ""
Write-Host "=== USBPcap Start value ==="
$val = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\USBPcap" -ErrorAction SilentlyContinue).Start
Write-Host ("USBPcap Start: " + $val + " (4=Disabled)")

Write-Host ""
Write-Host "=== DISM status ==="
$dism = Get-Process -Name dism -ErrorAction SilentlyContinue
if ($dism) {
    $runtime = [math]::Round(((Get-Date) - $dism.StartTime).TotalMinutes, 1)
    Write-Host ("DISM running - PID: $($dism.Id), Runtime: $runtime min")
} else {
    Write-Host "DISM has completed"
    Write-Host ""
    Write-Host "=== DISM log tail ==="
    Get-Content "C:\Windows\Logs\DISM\dism.log" -Tail 5
}

Write-Host ""
Write-Host "=== SFC check ==="
$sfc = Get-Process -Name sfc -ErrorAction SilentlyContinue
if ($sfc) { Write-Host "SFC still running" } else { Write-Host "SFC not running" }

Write-Host ""
Write-Host "Press Enter..."
Read-Host
