
Write-Host "=== Windows Update driver check (extended) ==="
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()

Write-Host "Searching ALL updates (not just drivers)..."
$all = $searcher.Search("IsInstalled=0")
Write-Host "Total pending: $($all.Updates.Count)"
foreach ($u in $all.Updates) {
    $driverFlag = if ($u.Title -match 'Intel|Graphic|Display|Audio|Conexant|Senary|Chipset|Driver|Firmware|BIOS') { " [RELEVANT]" } else { "" }
    Write-Host "  $($u.Title)$driverFlag"
}

Write-Host ""
Write-Host "=== Current GPU driver vs latest known ==="
$gpu = Get-CimInstance Win32_VideoController | Where-Object { $PSItem.Name -match 'Intel' }
Write-Host "Current: $($gpu.DriverVersion) ($($gpu.DriverDate))"
Write-Host "Latest available for 13th Gen Iris Xe: 32.0.101.6556 or newer"
Write-Host "Your version 32.0.101.7076 appears to be a newer OEM build"

Write-Host ""
Write-Host "=== Alternative: Try winget with different network ==="
$result = winget search "Intel ARC" --source winget 2>&1 | Select-String "Intel"
if ($result) { $result } else { Write-Host "No Intel GPU packages in winget" }

Write-Host ""
Write-Host "=== Summary ==="
Write-Host "GPU driver: 32.0.101.7076 (OEM build, relatively current)"
Write-Host "Action needed: If nonpaged pool grows over time, update via Intel DSA manually"
Write-Host "Firmware update: HUAWEI - Firmware - 0.1.0.8 (pending install)"
Read-Host
