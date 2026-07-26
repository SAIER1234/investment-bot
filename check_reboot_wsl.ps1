
Write-Host "=== Pending reboot? ==="
$rebootPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\PostRebootReporting"
)
$needReboot = $false
foreach ($path in $rebootPaths) {
    if (Test-Path $path) {
        Write-Host "REBOOT REQUIRED: $path"
        $needReboot = $true
    }
}
if (-not $needReboot) { Write-Host "No reboot pending in registry" }

Write-Host ""
Write-Host "=== BIOS info ==="
Get-CimInstance Win32_BIOS | Select-Object Manufacturer, SMBIOSBIOSVersion, ReleaseDate | Format-List

Write-Host ""
Write-Host "=== WSL ==="
wsl --list --verbose

Write-Host ""
Write-Host "=== vmmemWSL memory ==="
$wsl = Get-Process -Name vmmemWSL -ErrorAction SilentlyContinue
if ($wsl) {
    $mb = [math]::Round($wsl.WorkingSet64/1MB, 1)
    Write-Host "vmmemWSL: $mb MB"
} else { Write-Host "vmmemWSL not running" }

Write-Host ""
Write-Host "=== Windows Update history (last 3) ==="
$wuHistory = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WindowsUpdateClient'; Id=19} -MaxEvents 5 -ErrorAction SilentlyContinue
foreach ($e in $wuHistory) {
    if ($e.Message -match '安装成功' -or $e.Message -match 'Installation Successful') {
        Write-Host $e.TimeCreated
        if ($e.Message -match 'HUAWEI|Firmware|固件') {
            Write-Host "  >>> FIRMWARE UPDATE INSTALLED <<<"
        }
    }
}

Write-Host ""
Write-Host "Press Enter..."
Read-Host
