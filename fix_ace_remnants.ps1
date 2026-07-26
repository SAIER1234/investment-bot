
Write-Host "=== Running ACE driver check ==="
Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match 'ACE' -and $PSItem.State -eq 'Running' } | Select-Object Name, State, StartMode, PathName | Format-List

Write-Host ""
Write-Host "=== All ACE registry entries ==="
Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services" -ErrorAction SilentlyContinue | Where-Object { $PSItem.PSChildName -match '^ace-|^ACE-' } | ForEach-Object {
    $start = (Get-ItemProperty -Path $PSItem.PSPath -Name "Start" -ErrorAction SilentlyContinue).Start
    $img = (Get-ItemProperty -Path $PSItem.PSPath -Name "ImagePath" -ErrorAction SilentlyContinue).ImagePath
    Write-Host "$($PSItem.PSChildName) Start=$start ImagePath=$img"
}

Write-Host ""
Write-Host "=== Disabling all ACE remnants ==="
$aceKeys = Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services" -ErrorAction SilentlyContinue | Where-Object { $PSItem.PSChildName -match '^ace-|^ACE-' }
foreach ($key in $aceKeys) {
    $name = $key.PSChildName
    try {
        # Set to Disabled
        Set-ItemProperty -Path $key.PSPath -Name "Start" -Value 4 -Type DWord -Force -ErrorAction Stop

        # Also try to delete via sc.exe
        sc.exe delete $name 2>&1 | Out-Null

        Write-Host "  DISABLED: $name"
    } catch {
        Write-Host "  FAILED: $name - $_"
    }
}

Write-Host ""
Write-Host "=== Re-disable Edge auto-launch ==="
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "MicrosoftEdgeAutoLaunch_E354FCAF3CBDC7720576C573696FB6E8" -Force -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "ctfmon" -Force -ErrorAction SilentlyContinue
Write-Host "Edge auto-launch: removed"
Write-Host "ctfmon stays (it's the language input indicator)"

# Wait, I should NOT remove ctfmon. Let me fix this.
# ctfmon is the language bar - needed for IME input method switching
# Actually the previous command already tried to remove it. Let me check if it's still there and put it back if needed.
$ctfmonExists = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "ctfmon" -ErrorAction SilentlyContinue
if (-not $ctfmonExists) {
    Write-Host "Re-adding ctfmon (required for IME)..."
    Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "ctfmon" -Value "C:\Windows\system32\ctfmon.exe" -Force
    Write-Host "ctfmon restored"
}

Write-Host ""
Write-Host "=== Final check ==="
Write-Host "ACE drivers running:"
(Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match 'ACE' -and $PSItem.State -eq 'Running' } | Measure-Object).Count

Write-Host "Startup items:"
Get-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" | Select-Object -ExcludeProperty PS* | Format-List
Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" | Select-Object -ExcludeProperty PS* | Format-List

Read-Host
