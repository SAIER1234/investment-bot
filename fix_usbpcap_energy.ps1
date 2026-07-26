
Write-Host "=== Fix 1: Disabling USBPcap driver to stop 156 daily hcmon conflicts ==="
if (Test-Path "HKLM:\SYSTEM\CurrentControlSet\Services\USBPcap") {
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\USBPcap" -Name "Start" -Value 4 -Type DWord -Force
    Write-Host "USBPcap driver set to Disabled (Start=4)"
} else {
    Write-Host "USBPcap registry not found - checking alternative paths..."
    $found = Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services\" -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match 'USBPcap|usbpcap' }
    if ($found) {
        Write-Host "Found: $($found.PSChildName)"
        Set-ItemProperty -Path $found.PSPath -Name "Start" -Value 4 -Type DWord -Force
        Write-Host "Disabled"
    } else {
        Write-Host "USBPcap not found as service - driver file exists but no service key"
        Write-Host "Checking for service key in ControlSet001..."
        if (Test-Path "HKLM:\SYSTEM\ControlSet001\Services\USBPcap") {
            Set-ItemProperty -Path "HKLM:\SYSTEM\ControlSet001\Services\USBPcap" -Name "Start" -Value 4 -Type DWord -Force
            Write-Host "Found and disabled in ControlSet001"
        }
    }
}

Write-Host ""
Write-Host "=== Fix 2: Setting Energy Server Service to Manual to stop daily crashes ==="
$energyServices = @('ESRV_SVC_QUEENCREEK', 'SystemUsageReportSvc_QUEENCREEK')
foreach ($svcName in $energyServices) {
    try {
        Set-Service -Name $svcName -StartupType Manual -ErrorAction Stop
        Stop-Service -Name $svcName -Force -ErrorAction SilentlyContinue
        Write-Host "$svcName : set to Manual and stopped"
    } catch {
        Write-Host "$svcName : FAILED - $_"
    }
}

Write-Host ""
Write-Host "=== Final status ==="
$svc1 = Get-Service -Name ESRV_SVC_QUEENCREEK -ErrorAction SilentlyContinue
if ($svc1) { Write-Host ("ESRV_SVC_QUEENCREEK: " + $svc1.Status + " / " + $svc1.StartType) }

$usbStart = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\USBPcap" -ErrorAction SilentlyContinue).Start
if ($usbStart) { Write-Host ("USBPcap Start value: " + $usbStart + " (4=Disabled)") }

# Check DISM
$dism = Get-Process -Name dism -ErrorAction SilentlyContinue
if ($dism) { Write-Host "DISM still running..." } else { Write-Host "DISM has completed" }

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
