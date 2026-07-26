Write-Host "=== Energy Server Service ==="
$svc = Get-Service -Name ESRV_SVC_QUEENCREEK -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host ("Name: " + $svc.Name)
    Write-Host ("Display: " + $svc.DisplayName)
    Write-Host ("Status: " + $svc.Status)
    Write-Host ("StartType: " + $svc.StartType)
}
Write-Host ""

Write-Host "=== Service DLL path ==="
$reg = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\ESRV_SVC_QUEENCREEK" -ErrorAction SilentlyContinue
if ($reg) { Write-Host ("ImagePath: " + $reg.ImagePath) }
Write-Host ""

Write-Host "=== All queencreek services ==="
Get-Service | Where-Object { $_.Name -match 'queencreek' } | Select-Object Name, DisplayName, Status, StartType | Format-Table -AutoSize -Wrap
Write-Host ""

Write-Host "=== Energy Server crash events (last 7 days) ==="
$events = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Service Control Manager'; Id=7034} -MaxEvents 100 -ErrorAction SilentlyContinue
foreach ($e in $events) {
    if ($e.Message -match 'Energy Server|ESRV_SVC') {
        Write-Host ($e.TimeCreated.ToString() + " - Energy Server Service crashed")
    }
}

Write-Host ""
Write-Host "=== USBPcap service check ==="
Get-Service -Name *usbpcap*,*npcap* -ErrorAction SilentlyContinue | Format-Table Name, Status, StartType -AutoSize
Write-Host ""
Write-Host "=== hcmon crash/error events (today) ==="
$hcmonEvents = Get-EventLog -LogName System -Source hcmon -Newest 10 -ErrorAction SilentlyContinue
if ($hcmonEvents) {
    foreach ($e in $hcmonEvents) {
        Write-Host ($e.TimeGenerated.ToString() + " - " + $e.EntryType + " - " + ($e.Message -replace '\n',' ').Substring(0, [Math]::Min(150, $e.Message.Length)))
    }
}
Write-Host ""
Write-Host "=== DISM status ==="
$dism = Get-Process -Name dism -ErrorAction SilentlyContinue
if ($dism) { Write-Host "DISM still running (PID: $($dism.Id), started: $($dism.StartTime))" } else { Write-Host "DISM has finished" }

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
