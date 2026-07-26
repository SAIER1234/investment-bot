Write-Host "=== SFC status ==="
$sfc = Get-Process -Name sfc -ErrorAction SilentlyContinue
if ($sfc) { Write-Host ("SFC running - PID: " + $sfc.Id) }
else { Write-Host "SFC NOT running" }

Write-Host ""
Write-Host "=== DISM status ==="
$dism = Get-Process -Name dism -ErrorAction SilentlyContinue
if ($dism) { Write-Host ("DISM running - PID: " + $dism.Id) }
else { Write-Host "DISM NOT running" }

Write-Host ""
Write-Host "=== Most recent SFC CBS entry ==="
if (Test-Path "C:\Windows\Logs\CBS\CBS.log") {
    Get-Content "C:\Windows\Logs\CBS\CBS.log" -Tail 2
} else {
    Write-Host "CBS.log not found"
}

Write-Host ""
Write-Host "=== DISM log tail ==="
if (Test-Path "C:\Windows\Logs\DISM\dism.log") {
    Get-Content "C:\Windows\Logs\DISM\dism.log" -Tail 3
}
Read-Host
