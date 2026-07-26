
Write-Host "=== Running SFC /scannow ==="
sfc /scannow
Write-Host ""
Write-Host "SFC completed."

Write-Host ""
Write-Host "=== Running DISM restorehealth ==="
dism /online /cleanup-image /restorehealth
Write-Host ""
Write-Host "DISM completed."

Write-Host ""
Write-Host "=== Result ==="
Write-Host "SFC and DISM both completed."
Write-Host ""
Write-Host "Press Enter to exit..."
Read-Host
