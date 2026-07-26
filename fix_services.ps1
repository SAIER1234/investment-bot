# Stop leaking Huawei services
Stop-Service -Name HiConnectivityService -Force -ErrorAction SilentlyContinue
Stop-Service -Name HwDistributedMainService -Force -ErrorAction SilentlyContinue
Stop-Service -Name HWSyncService -Force -ErrorAction SilentlyContinue
Stop-Service -Name MBAMainService -Force -ErrorAction SilentlyContinue
Stop-Service -Name ShellHWDetection -Force -ErrorAction SilentlyContinue
Stop-Service -Name HuaweiHiSuiteService64.exe -Force -ErrorAction SilentlyContinue

# Disable auto-start
Set-Service -Name HiConnectivityService -StartupType Disabled
Set-Service -Name HwDistributedMainService -StartupType Disabled
Set-Service -Name HWSyncService -StartupType Disabled
Set-Service -Name MBAMainService -StartupType Disabled
Set-Service -Name ShellHWDetection -StartupType Disabled
Set-Service -Name HuaweiHiSuiteService64.exe -StartupType Disabled

# Disable recovery restart
cmd /c 'sc.exe failure HiConnectivityService reset= 0 actions= ""' 2>$null
cmd /c 'sc.exe failure HwDistributedMainService reset= 0 actions= ""' 2>$null

# Disable problematic drivers
cmd /c 'sc.exe config SbieDrv start= disabled' 2>$null
cmd /c 'sc.exe config TxQBService start= disabled' 2>$null

# Disable hibernation (frees 6GB)
powercfg /hibernate off

# Disable unnecessary startup items
Remove-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "vmware-tray.exe" -Force -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "ACE-Tray" -Force -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "MTPW" -Force -ErrorAction SilentlyContinue

Write-Host "=== Results ==="
Get-Service -Name HiConnectivityService, HwDistributedMainService, HWSyncService, MBAMainService, ShellHWDetection, HuaweiHiSuiteService64.exe | Select-Object Name, Status, StartType | Format-Table -AutoSize

Write-Host "Free memory before/after suggested reboot should improve ~2-3 GB"
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
