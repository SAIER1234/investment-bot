
Write-Host "Killing HiConnectivityService process..."
taskkill /f /im HiConnectivityService.exe 2>$null
Start-Sleep -Seconds 2

Write-Host "Disabling service via registry..."
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\HiConnectivityService" -Name "Start" -Value 4 -Type DWord -Force

Write-Host "Disabling recovery actions..."
cmd /c 'sc.exe failure HiConnectivityService reset= 0 actions= ""' 2>$null

Write-Host "Stopping service..."
Stop-Service -Name HiConnectivityService -Force -ErrorAction SilentlyContinue
sc.exe stop HiConnectivityService 2>$null

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "=== Final Status ==="
$svc = Get-Service -Name HiConnectivityService
Write-Host "Status: $($svc.Status)"
Write-Host "StartType: $($svc.StartType)"
$proc = Get-Process -Name HiConnectivityService -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "WARNING: Process still running! $([math]::Round($proc.WorkingSet64/1MB,1)) MB"
} else {
    Write-Host "Process killed! ~1.2 GB committed memory freed."
}

$os = Get-CimInstance Win32_OperatingSystem
Write-Host ""
Write-Host "Free Physical Memory: $([math]::Round($os.FreePhysicalMemory/1MB,1)) GB"

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
