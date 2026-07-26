
Write-Host "=== ANTIVIRUS CONFLICT CHECK ==="

Write-Host ""
Write-Host "--- Windows Defender status ---"
$defStatus = Get-MpComputerStatus -ErrorAction SilentlyContinue
if ($defStatus) {
    Write-Host "AntivirusEnabled: $($defStatus.AntivirusEnabled)"
    Write-Host "AntivirusSignatureVersion: $($defStatus.AntivirusSignatureVersion)"
    Write-Host "RealTimeProtectionEnabled: $($defStatus.RealTimeProtectionEnabled)"
    Write-Host "BehaviorMonitorEnabled: $($defStatus.BehaviorMonitorEnabled)"
    Write-Host "OnAccessProtectionEnabled: $($defStatus.OnAccessProtectionEnabled)"
    Write-Host "IoavProtectionEnabled: $($defStatus.IoavProtectionEnabled)"
    Write-Host "NISEnabled: $($defStatus.NISEnabled)"
    Write-Host ""
    Write-Host "Defender process memory:"
    $def = Get-Process -Name MsMpEng -ErrorAction SilentlyContinue
    if ($def) {
        Write-Host "  WorkingSet: $([math]::Round($def.WorkingSet64/1MB,1)) MB"
        Write-Host "  PrivateBytes: $([math]::Round($def.PrivateMemorySize64/1MB,1)) MB"
    }
} else {
    Write-Host "Defender not accessible (may be disabled by group policy)"
}

Write-Host ""
Write-Host "--- Kaspersky status ---"
$kasperskyServices = Get-Service | Where-Object { $PSItem.Name -like '*kav*' -or $PSItem.Name -like '*kl*' -or $PSItem.DisplayName -like '*Kaspersky*' }
Write-Host "Kaspersky services:"
$kasperskyServices | Select-Object Name, DisplayName, Status, StartType | Format-Table -AutoSize -Wrap

Write-Host ""
Write-Host "Kaspersky running drivers:"
$klDrivers = Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -like 'kl*' -and $PSItem.State -eq 'Running' }
$klDrivers | Select-Object Name, DisplayName, @{N='Path';E={$PSItem.PathName}} | Format-Table -AutoSize -Wrap
Write-Host "Total Kaspersky kernel drivers: $($klDrivers.Count)"

Write-Host ""
Write-Host "--- Windows Security Center registered AV ---"
try {
    $wmiAv = Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction Stop
    foreach ($av in $wmiAv) {
        Write-Host "Registered AV: $($av.displayName)"
        Write-Host "  Product State: $($av.productState)"
        Write-Host "  GUID: $($av.instanceGuid)"
    }
} catch {
    Write-Host "WMI SecurityCenter not accessible"
}

Write-Host ""
Write-Host "--- ASSESSMENT ---"
$defRunning = Get-Process -Name MsMpEng -ErrorAction SilentlyContinue
$klRunning = Get-Process -Name avp -ErrorAction SilentlyContinue
if ($defRunning -and $klRunning) {
    Write-Host "! DUAL AV ACTIVE: Both Defender and Kaspersky running simultaneously"
    Write-Host "! This causes: double file scanning, competing kernel drivers,"
    Write-Host "! excessive nonpaged pool consumption (each AV allocates pool)"
    Write-Host ""
    Write-Host "RECOMMENDATION: Uninstall Kaspersky OR disable Defender"
    Write-Host "  Defender alone on Win11 is sufficient for most users"
} elseif ($klRunning) {
    Write-Host "Kaspersky running, Defender in passive mode (normal)"
} else {
    Write-Host "Only Defender running"
}

Read-Host
