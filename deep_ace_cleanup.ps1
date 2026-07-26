
Write-Host "=== Deep ACE + Filter Manager Cleanup ==="

Write-Host ""
Write-Host "--- 1. ACE filter errors since boot (detailed) ---"
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
Write-Host "Boot time: $bootTime"
$filterErrors = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-FilterManager'; StartTime=$bootTime} -MaxEvents 100 -ErrorAction SilentlyContinue
$aceErrors = $filterErrors | Where-Object { $PSItem.Message -match 'ACE' }
Write-Host "Total filter events since boot: $($filterErrors.Count)"
Write-Host "ACE-related filter events: $($aceErrors.Count)"

if ($aceErrors.Count -gt 0) {
    Write-Host ""
    Write-Host "Latest 5 ACE filter errors:"
    $aceErrors | Select-Object -First 5 TimeCreated, Id, @{N='Msg';E={($PSItem.Message -split '\n')[0]}} | Format-Table -AutoSize -Wrap
}

Write-Host ""
Write-Host "--- 2. Check if ACE filter is still registered ---"
$fltmc = fltmc filters 2>&1
$aceLines = $fltmc | Select-String 'ACE'
Write-Host "ACE filters in fltmc: $($aceLines.Count)"
if ($aceLines.Count -gt 0) {
    Write-Host $aceLines
} else {
    Write-Host "  No ACE filters registered!"
}

Write-Host ""
Write-Host "--- 3. Check ACE-CORE registry keys ---"
$coreKeys = Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services" -ErrorAction SilentlyContinue | Where-Object { $PSItem.PSChildName -match 'ACE-CORE|ACE-BOOT|ACE-BASE|ACE-GAME|ACE-ADVT' }
Write-Host "ACE driver keys: $($coreKeys.Count)"
foreach ($k in $coreKeys) {
    Write-Host "  $($k.PSChildName)"
}

Write-Host ""
Write-Host "--- 4. Clean ace-game-0 remnant ---"
$aceGame0 = "HKLM:\SYSTEM\CurrentControlSet\Services\ace-game-0"
if (Test-Path $aceGame0) {
    Set-ItemProperty -Path $aceGame0 -Name "Start" -Value 4 -Type DWord -Force -ErrorAction SilentlyContinue
    Write-Host "ace-game-0: set to Disabled"
}

Write-Host ""
Write-Host "--- 5. Nonpaged pool: what drivers are using it? ---"
Write-Host "(Using driverquery, filtering top NP consumers)"
$dq = driverquery /v /fo csv 2>$null | ConvertFrom-Csv
$topNp = $dq | Where-Object { $PSItem.'NP Paged(KB)' -and [int]($PSItem.'NP Paged(KB)' -replace ',','0') -gt 100000 } | Sort-Object {[int]($PSItem.'NP Paged(KB)' -replace ',','0')} -Descending | Select-Object -First 10 'Module Name', 'Display Name', 'NP Paged(KB)'
if ($topNp) {
    Write-Host "Drivers with >100 MB nonpaged pool:"
    foreach ($d in $topNp) {
        $mb = [math]::Round([int]($d.'NP Paged(KB)' -replace ',','0')/1024, 1)
        Write-Host "  $($d.'Module Name'.PadRight(25)) $mb MB - $($d.'Display Name')"
    }
} else {
    Write-Host "No driver above 100 MB - nonpaged pool distributed across many small allocations"
}

Write-Host ""
Write-Host "--- 6. System uptime ---"
$uptime = [math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours, 1)
Write-Host "Uptime: $uptime hours"

Write-Host ""
Write-Host "--- 7. Check for new ACE events after uninstall (last 30 min) ---"
$thirtyMinAgo = (Get-Date).AddMinutes(-30)
$recentAce = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-FilterManager'; StartTime=$thirtyMinAgo} -MaxEvents 50 -ErrorAction SilentlyContinue | Where-Object { $PSItem.Message -match 'ACE' }
Write-Host "ACE filter events in last 30 min: $($recentAce.Count)"
if ($recentAce.Count -eq 0) { Write-Host "  STOPPED - old events are from before uninstall" }
else { Write-Host "  STILL ACTIVE!" }

Read-Host
