Write-Host "=== Energy Server Service search ==="
Get-Service | Where-Object { $_.Name -match 'energy|queencreek' } | Select-Object Name, DisplayName, Status, StartType | Format-Table -AutoSize

Write-Host ""
Write-Host "=== Intel Graphics Driver ==="
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, DriverDate | Format-List

Write-Host ""
Write-Host "=== Audio drivers ==="
Get-CimInstance Win32_SoundDevice | Where-Object { $_.Status -eq 'OK' } | Select-Object Name, Manufacturer | Format-Table -AutoSize -Wrap

Write-Host ""
Write-Host "=== Check Windows Update for driver updates ==="
try {
    $updates = Get-CimInstance -Namespace root/Microsoft/Windows/WindowsUpdate -ClassName MSFT_WUUpdate -ErrorAction Stop
    $driverUpdates = $updates | Where-Object { $_.Title -match 'Intel|Graphic|Display|Conexant|Audio|Senary|Chipset|Sensor' }
    if ($driverUpdates) {
        $driverUpdates | Select-Object -First 10 Title | Format-Table -AutoSize -Wrap
    } else {
        Write-Host "No driver updates found via WU API"
    }
} catch {
    Write-Host "WU API query failed, trying wuauclt..."
    # Fallback: check WU history
    Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WindowsUpdateClient'} -MaxEvents 5 -ErrorAction SilentlyContinue | Select-Object TimeCreated, Id, @{N='Msg';E={($_.Message -split '\n')[0]}} | Format-Table -AutoSize
}

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
