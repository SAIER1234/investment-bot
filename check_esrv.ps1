
Write-Host "=== Intel SUR esrv.exe ==="
$esrvProcs = Get-Process -Name esrv -ErrorAction SilentlyContinue
if ($esrvProcs) {
    foreach ($p in $esrvProcs) {
        Write-Host "PID: $($p.Id)"
        Write-Host "Path: $($p.Path)"
        Write-Host "Mem: $([math]::Round($p.WorkingSet64/1MB,1)) MB"
    }
} else { Write-Host "NOT running" }

Write-Host ""
Write-Host "=== SUR services ==="
Get-Service -Name *SUR*,*SystemUsageReport* -ErrorAction SilentlyContinue | Format-Table Name, DisplayName, Status, StartType -AutoSize

Write-Host ""
Write-Host "=== SbieDrv check ==="
$sb = Get-Service -Name SbieDrv -ErrorAction SilentlyContinue
if ($sb) { Write-Host "SbieDrv: $($sb.Status) / $($sb.StartType)" }
else { Write-Host "SbieDrv: not found" }

Write-Host ""
Write-Host "=== Thermal check (if available) ==="
try {
    $thermal = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop
    foreach ($t in $thermal) {
        $tempC = [math]::Round($t.CurrentTemperature/10 - 273.15, 1)
        Write-Host "$($t.InstanceName): $tempC C"
    }
} catch {
    Write-Host "Thermal sensors not available via WMI"
}

Read-Host
