
Write-Host "=== ACE (AntiCheat Expert) Investigation ==="

Write-Host ""
Write-Host "--- ACE Services ---"
Get-Service -Name *ACE*,*AntiCheat* -ErrorAction SilentlyContinue | Select-Object Name, DisplayName, Status, StartType | Format-Table -AutoSize

Write-Host ""
Write-Host "--- ACE Drivers ---"
Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match 'ACE' -or $PSItem.DisplayName -match 'AntiCheat' } | Select-Object Name, DisplayName, State, StartMode, @{N='Path';E={$PSItem.PathName}} | Format-Table -AutoSize -Wrap

Write-Host ""
Write-Host "--- ACE Registry entries ---"
$aceKeys = Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Services" -ErrorAction SilentlyContinue | Where-Object { $PSItem.PSChildName -match 'ACE' }
foreach ($key in $aceKeys) {
    Write-Host ""
    Write-Host "Key: $($key.PSChildName)"
    try {
        $img = (Get-ItemProperty -Path $key.PSPath -Name "ImagePath" -ErrorAction SilentlyContinue).ImagePath
        $start = (Get-ItemProperty -Path $key.PSPath -Name "Start" -ErrorAction SilentlyContinue).Start
        Write-Host "  ImagePath: $img"
        Write-Host "  Start: $start (0=boot 1=system 2=auto 3=manual 4=disabled)"
    } catch {
        Write-Host "  Could not read properties"
    }
}

Write-Host ""
Write-Host "--- ACE Filter Manager errors (today) ---"
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$aceErrors = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-FilterManager'; StartTime=$bootTime} -MaxEvents 50 -ErrorAction SilentlyContinue | Where-Object { $PSItem.Message -match 'ACE-CORE' }
Write-Host "ACE filter errors since boot: $($aceErrors.Count)"
foreach ($e in $aceErrors | Select-Object -First 5) {
    Write-Host "  $($e.TimeCreated) - Id=$($e.Id)"
    if ($e.Message -match "ACE-CORE(\d+)") {
        Write-Host "    Driver: ACE-CORE$($Matches[1])"
    }
}

Write-Host ""
Write-Host "--- ACE file locations ---"
$acePaths = @(
    "C:\Program Files\AntiCheatExpert",
    "C:\Program Files (x86)\AntiCheatExpert",
    "C:\Windows\System32\drivers\ACE*.sys"
)
foreach ($p in $acePaths) {
    if (Test-Path $p) {
        Write-Host "FOUND: $p"
        Get-ChildItem $p -ErrorAction SilentlyContinue | Select-Object Name, Length | Format-Table -AutoSize
    }
}

Write-Host ""
Write-Host "--- Other game anti-cheat services ---"
Get-Service -Name *Vanguard*,*vgk*,*vgc*,*EasyAntiCheat*,*BattlEye*,*EAC* -ErrorAction SilentlyContinue | Select-Object Name, DisplayName, Status, StartType | Format-Table -AutoSize

Write-Host ""
Write-Host "--- Game anti-cheat drivers ---"
Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -match 'vgk|vgc|EasyAntiCheat|BattlEye|BEDaisy|ACE-CORE|EAC' } | Select-Object Name, DisplayName, State, StartMode | Format-Table -AutoSize

Read-Host
