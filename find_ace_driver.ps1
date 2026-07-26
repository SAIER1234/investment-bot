
$aceDrv = Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match 'ACE' -and $PSItem.State -eq 'Running' }
foreach ($d in $aceDrv) {
    Write-Host "Name: $($d.Name)"
    Write-Host "State: $($d.State)"
    Write-Host "StartMode: $($d.StartMode)"
    Write-Host "Path: $($d.PathName)"
    Write-Host "DisplayName: $($d.DisplayName)"
    Write-Host ""
}

Write-Host "All ACE-related driver entries (any state):"
Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match 'ACE' } | Select-Object Name, State, StartMode | Format-Table -AutoSize

Write-Host ""
Write-Host "Registry entries:"
Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services" | Where-Object { $PSItem.PSChildName -match '^ace-|^ACE-' } | ForEach-Object {
    $n = $PSItem.PSChildName
    $s = (Get-ItemProperty -Path $PSItem.PSPath -Name "Start" -ErrorAction SilentlyContinue).Start
    Write-Host "$n Start=$s"
}

Write-Host ""
Write-Host "Filetrace/spaceparser/spaceport are Microsoft, NOT ACE:"
Write-Host "  Filetrace = Microsoft Fileserver tracer driver"
Write-Host "  spaceparser = Microsoft Storage Spaces driver"
Write-Host "  spaceport = Microsoft Storage Spaces port driver"
Read-Host
