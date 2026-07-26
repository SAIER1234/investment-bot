
Write-Host "=== Virtualization features ==="
$features = @('VirtualMachinePlatform','HypervisorPlatform','Microsoft-Windows-Subsystem-Linux')
foreach ($f in $features) {
    $state = Get-WindowsOptionalFeature -Online -FeatureName $f -ErrorAction SilentlyContinue
    if ($state) {
        $mark = if ($state.State -eq 'Enabled') { 'OK' } else { 'DISABLED' }
        Write-Host "$mark`: $f = $($state.State)"
    } else {
        Write-Host "  ? $f = not found"
    }
}

Write-Host ""
Write-Host "=== Reboot required? ==="
$rebootPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"
)
$needReboot = $false
foreach ($p in $rebootPaths) {
    if (Test-Path $p) { Write-Host "REBOOT REQUIRED: $p"; $needReboot = $true }
}
if (-not $needReboot) { Write-Host "No pending reboot detected" }

Write-Host ""
Write-Host "=== BCD hypervisorlaunchtype ==="
bcdedit /enum {current} 2>&1 | Select-String "hypervisorlaunchtype"

Write-Host ""
Write-Host "=== VMware + WSL coexistence check ==="
$vmp = (Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform).State -eq 'Enabled'
$whp = (Get-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform).State -eq 'Enabled'
$wsl = (Get-WindowsOptionalFeature -Online -FeatureName 'Microsoft-Windows-Subsystem-Linux').State -eq 'Enabled'
$vmware = Test-Path "C:\Program Files\VMware\VMware Workstation\vmware.exe"

Write-Host "VirtualMachinePlatform: $vmp"
Write-Host "HypervisorPlatform: $whp"
Write-Host "WSL: $wsl"
Write-Host "VMware: $vmware"

if ($vmp -and $whp -and $vmware) {
    Write-Host ""
    Write-Host "CONFIGURATION: CORRECT"
    Write-Host "VMware can now coexist with Hyper-V/WSL2 via WHP."
    Write-Host "Reboot to apply."
} elseif ($vmp -and -not $whp -and $vmware) {
    Write-Host ""
    Write-Host "CONFIGURATION: CONFLICT"
    Write-Host "VMware + Hyper-V fighting over VT-x = system freeze"
    Write-Host "Enable HypervisorPlatform to fix!"
} else {
    Write-Host ""
    Write-Host "CONFIGURATION: other state"
    Write-Host "Check each component status"
}

Read-Host
