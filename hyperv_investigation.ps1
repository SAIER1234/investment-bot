
Write-Host "============================================"
Write-Host "  HYPER-V / WSL2 CRASH INVESTIGATION"
Write-Host "============================================"

Write-Host ""
Write-Host "--- 1. Hyper-V status ---"
$hyperv = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -ErrorAction SilentlyContinue
Write-Host "Hyper-V feature installed: $($hyperv.State)"

Write-Host ""
Write-Host "--- 2. Virtual Machine Platform ---"
$vmp = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -ErrorAction SilentlyContinue
Write-Host "VirtualMachinePlatform: $($vmp.State)"

Write-Host ""
Write-Host "--- 3. Windows Hypervisor Platform ---"
$whp = Get-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -ErrorAction SilentlyContinue
Write-Host "HypervisorPlatform: $($whp.State)"

Write-Host ""
Write-Host "--- 4. WSL version ---"
wsl --version 2>&1

Write-Host ""
Write-Host "--- 5. WSL status ---"
wsl --list --verbose 2>&1

Write-Host ""
Write-Host "--- 6. Hyper-V Event 167 details ---"
$hvEvents = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Hyper-V-Hypervisor'; Id=167} -MaxEvents 10 -ErrorAction SilentlyContinue
Write-Host "Total Event 167 occurrences: $($hvEvents.Count)"
foreach ($e in $hvEvents | Select-Object -First 5) {
    Write-Host ""
    Write-Host "Time: $($e.TimeCreated)"
    Write-Host "Message:"
    Write-Host $e.Message
}

Write-Host ""
Write-Host "--- 7. Hyper-V related features enabled ---"
$features = @(
    'Microsoft-Hyper-V',
    'Microsoft-Hyper-V-Management-PowerShell',
    'Microsoft-Hyper-V-Tools-All',
    'VirtualMachinePlatform',
    'HypervisorPlatform',
    'Containers-DisposableClientVM',
    'Microsoft-Windows-Subsystem-Linux'
)
foreach ($f in $features) {
    $state = Get-WindowsOptionalFeature -Online -FeatureName $f -ErrorAction SilentlyContinue
    if ($state) {
        Write-Host "$f`: $($state.State)"
    }
}

Write-Host ""
Write-Host "--- 8. Check if Hyper-V hypervisor is actually running ---"
try {
    $hv = Get-CimInstance -Namespace root\virtualization\v2 -ClassName Msvm_ComputerSystem -ErrorAction Stop
    Write-Host "Hyper-V management accessible"
    Write-Host "VMs running: $($hv.Count)"
} catch {
    Write-Host "Hyper-V WMI not accessible (hypervisor may not be fully configured)"
}

Write-Host ""
Write-Host "--- 9. Memory allocation - check if Hyper-V is reserving memory ---"
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "Total visible: $([math]::Round($os.TotalVisibleMemorySize/1MB,1)) GB"
Write-Host "Free physical: $([math]::Round($os.FreePhysicalMemory/1MB,1)) GB"

Write-Host ""
Write-Host "--- 10. vmmem process (WSL2 VM) ---"
$vmmem = Get-Process -Name vmmem* -ErrorAction SilentlyContinue
if ($vmmem) {
    Write-Host "vmmem running: $($vmmem.Count) instances"
    foreach ($v in $vmmem) {
        Write-Host "  PID: $($v.Id) WorkingSet: $([math]::Round($v.WorkingSet64/1MB,1)) MB Private: $([math]::Round($v.PrivateMemorySize64/1MB,1)) MB"
    }
} else {
    Write-Host "vmmem NOT running"
}

Write-Host ""
Write-Host "--- 11. BCD hypervisorlaunchtype ---"
bcdedit /enum {current} 2>&1 | Select-String "hypervisorlaunchtype"

Write-Host ""
Write-Host "--- ASSESSMENT ---"
Write-Host "Event 167 appears 2-4 seconds before EVERY crash."
Write-Host "This is the Hyper-V hypervisor reporting a failure."
Write-Host ""
Write-Host "Possible causes:"
Write-Host "  1. WSL2 VM exhausting available memory"
Write-Host "  2. Hyper-V incompatibility with certain drivers (Kaspersky was one)"
Write-Host "  3. SLAT/VMX conflict with other virtualization (VMware?)"
Write-Host "  4. Hypervisor memory fragmentation"

Read-Host
