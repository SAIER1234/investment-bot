
Write-Host "============================================"
Write-Host "  PHASE 2+3: CLEANUP + HARDWARE FIXES"
Write-Host "============================================"

Write-Host ""
Write-Host "--- 1. Disable USB Selective Suspend ---"
Write-Host "This prevents E: drive from spinning down and causing I/O delays"
powercfg /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /setactive SCHEME_CURRENT
Write-Host "USB Selective Suspend: DISABLED (AC + DC)"

Write-Host ""
Write-Host "--- 2. Disable HDD sleep timer ---"
powercfg /change -disk-timeout-ac 0
powercfg /change -disk-timeout-dc 0
Write-Host "Disk timeout: NEVER (AC + DC)"

Write-Host ""
Write-Host "--- 3. Clean ace-game-0 ---"
$aceGamePath = "HKLM:\SYSTEM\CurrentControlSet\Services\ace-game-0"
if (Test-Path $aceGamePath) {
    Set-ItemProperty -Path $aceGamePath -Name "Start" -Value 4 -Type DWord -Force
    Write-Host "ace-game-0: set to Disabled"
}

Write-Host ""
Write-Host "--- 4. Delete SbieDrv service ---"
sc.exe delete SbieDrv 2>&1
Write-Host "SbieDrv: delete attempted"

Write-Host ""
Write-Host "--- 5. SSD Health ---"
Get-PhysicalDisk | Where-Object { $PSItem.MediaType -eq 'SSD' } | Select-Object FriendlyName, HealthStatus, OperationalStatus, MediaType, @{N='SizeGB';E={[math]::Round($PSItem.Size/1GB,1)}} | Format-List

Write-Host ""
Write-Host "--- 6. SSD chkdsk C: read-only scan ---"
Write-Host "(This just reads, safe)"
$result = chkdsk C: /scan 2>&1
Write-Host $result

Write-Host ""
Write-Host "--- 7. Schedule Windows Memory Diagnostic ---"
Write-Host "This will test RAM on next reboot"
try {
    Start-Process -FilePath "mdsched.exe" -ArgumentList "/restart" -Wait -ErrorAction SilentlyContinue
    Write-Host "Memory diagnostic scheduled"
} catch {
    Write-Host "Scheduling failed, will skip memory test"
}

Write-Host ""
Write-Host "--- 8. WUDFRd - check affected devices ---"
$wudfEvents = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-PnP'; Id=219; StartTime=(Get-Date).AddHours(-24)} -MaxEvents 20 -ErrorAction SilentlyContinue
$wudfEvents | Where-Object { $PSItem.Message -match 'WUDFRd' } | ForEach-Object {
    if ($PSItem.Message -match 'ACPI\\\\(SIL\w+)') { Write-Host "Device: $($Matches[1])" }
    if ($PSItem.Message -match 'STATUS_(\w+)') { Write-Host "  Error: $($Matches[1])" }
    Write-Host "  Time: $($PSItem.TimeCreated)"
}

Write-Host ""
Write-Host "--- 9. Check for Vanguard/other anti-cheat ---"
$antiCheatDrivers = Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match 'vgk|vgc|BEDaisy|EasyAntiCheat|BattlEye|EAC' -and $PSItem.State -eq 'Running' }
Write-Host "Running anti-cheat drivers: $($antiCheatDrivers.Count)"
if ($antiCheatDrivers.Count -gt 0) {
    foreach ($d in $antiCheatDrivers) { Write-Host "  ! $($d.Name)" }
}

Write-Host ""
Write-Host "--- 10. Check ALL non-Microsoft kernel drivers ---"
$thirdPartyDrv = Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.State -eq 'Running' -and $PSItem.PathName -notmatch 'Windows\\\\System32\\\\(drivers\\\\|DriverStore)' -and $PSItem.PathName -notmatch 'windows\\\\system32\\\\ntoskrnl' -and $PSItem.PathName -notmatch 'Windows\\\\System32\\\\Drivers\\\\[a-z]+\.(sys|SYS)' }
Write-Host "Third-party running drivers (non-stock): $($thirdPartyDrv.Count)"
$thirdPartyDrv | Sort-Object Name | Select-Object Name, @{N='Path';E={$PSItem.PathName}} | Format-Table -AutoSize -Wrap

Write-Host ""
Write-Host "--- 11. Thermal status ---"
try {
    $thermal = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop
    foreach ($t in $thermal) {
        $tempC = [math]::Round($t.CurrentTemperature/10 - 273.15, 1)
        Write-Host "Thermal Zone: $tempC C"
    }
} catch {
    Write-Host "No thermal data via WMI"
}
Write-Host "CPU temp estimate:"
$cpuLoad = (Get-CimInstance Win32_Processor).LoadPercentage
Write-Host "Current CPU load: $cpuLoad%"

Write-Host ""
Write-Host "--- 12. Power plan processor settings ---"
powercfg /query SCHEME_CURRENT SUB_PROCESSOR 54533251-82be-4824-96c1-47b60b740d00 2>&1 | Select-String 'maximum|minimum|Maximum|Minimum' -Context 0,0

Read-Host
