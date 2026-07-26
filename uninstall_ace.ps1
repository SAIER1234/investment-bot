
Write-Host "=== UNINSTALLING ACE (AntiCheat Expert) ==="
Write-Host ""

$acePath = "C:\Program Files\AntiCheatExpert"
$uninstaller = "$acePath\Uninstaller.exe"

if (Test-Path $uninstaller) {
    Write-Host "Running ACE uninstaller..."
    Write-Host "Path: $uninstaller"
    Write-Host ""

    # Run the uninstaller
    $process = Start-Process -FilePath $uninstaller -ArgumentList "/S" -Wait -NoNewWindow -PassThru -ErrorAction SilentlyContinue

    if ($process.ExitCode -eq 0) {
        Write-Host "Uninstaller completed successfully"
    } else {
        Write-Host "Uninstaller exit code: $($process.ExitCode)"
        Write-Host "Trying without /S flag..."
        Start-Process -FilePath $uninstaller -Wait -ErrorAction SilentlyContinue
    }

    Start-Sleep -Seconds 3

    # Verify uninstall
    if (Test-Path $acePath) {
        Write-Host ""
        Write-Host "ACE folder still exists. Force cleaning..."
        Write-Host "Stopping ACE services first..."

        # Stop all ACE services
        $aceSvcs = Get-Service -Name *ACE*,*AntiCheat* -ErrorAction SilentlyContinue
        foreach ($svc in $aceSvcs) {
            if ($svc.Status -ne 'Stopped') {
                Stop-Service -Name $svc.Name -Force -ErrorAction SilentlyContinue
                Write-Host "  Stopped: $($svc.Name)"
            }
        }

        # Disable all ACE drivers
        $aceDrivers = Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services" -ErrorAction SilentlyContinue | Where-Object { $PSItem.PSChildName -match '^ACE' }
        foreach ($drv in $aceDrivers) {
            Set-ItemProperty -Path $drv.PSPath -Name "Start" -Value 4 -Type DWord -Force -ErrorAction SilentlyContinue
            Write-Host "  Disabled: $($drv.PSChildName)"
        }

        Write-Host ""
        Write-Host "ACE drivers disabled. Reboot to fully unload them."
        Write-Host "Then you can manually delete: $acePath"
    } else {
        Write-Host ""
        Write-Host "ACE uninstalled successfully!"
    }
} else {
    Write-Host "ACE uninstaller not found at: $uninstaller"
    Write-Host "Trying via registry..."
    # Try to find via Programs and Features
    $aceApp = Get-CimInstance -ClassName Win32_Product -ErrorAction SilentlyContinue | Where-Object { $PSItem.Name -match 'AntiCheat' }
    if ($aceApp) {
        Write-Host "Found: $($aceApp.Name)"
        $aceApp.Uninstall()
    }
}

Write-Host ""
Write-Host "=== Verify ACE drivers after uninstall ==="
$remaining = Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match 'ACE-' -and $PSItem.State -eq 'Running' }
Write-Host "ACE drivers still running: $($remaining.Count)"
if ($remaining.Count -gt 0) {
    foreach ($d in $remaining) {
        Write-Host "  - $($d.Name) ($($d.State))"
    }
    Write-Host "These will be gone after reboot."
}

Write-Host ""
Read-Host "Press Enter..."
