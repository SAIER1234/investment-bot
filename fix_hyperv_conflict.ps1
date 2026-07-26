
Write-Host "============================================"
Write-Host "  FIX: HYPER-V + VMWARE CONFLICT"
Write-Host "============================================"

Write-Host ""
Write-Host "--- Current State ---"
Write-Host "VirtualMachinePlatform (WSL2 needs this): Enabled"
Write-Host "HypervisorPlatform (VMware needs this to coexist): Disabled"
Write-Host "VMware Workstation: Installed"
Write-Host "WSL2: Installed"

Write-Host ""
Write-Host "--- The Conflict ---"
Write-Host "WSL2 activates Hyper-V hypervisor."
Write-Host "VMware also wants VT-x/VMX."
Write-Host "When Hyper-V is active, VMware must use WHP (Windows Hypervisor Platform)."
Write-Host "But HypervisorPlatform is DISABLED!"
Write-Host "Result: VMware forces access → Hyper-V crashes → Event 167 → SYSTEM FREEZE"

Write-Host ""
Write-Host "--- Fix: Enable Windows Hypervisor Platform ---"
Write-Host "This allows VMware to coexist with Hyper-V/WSL2."
Write-Host ""

try {
    Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -All -NoRestart -ErrorAction Stop
    Write-Host "SUCCESS: Windows Hypervisor Platform enabled"
    Write-Host "REBOOT REQUIRED for this to take effect"
} catch {
    Write-Host "Enable failed, trying DISM..."
    try {
        dism /online /enable-feature /featurename:HypervisorPlatform /all /norestart
        Write-Host "DISM enable attempted"
    } catch {
        Write-Host "DISM also failed: $_"
    }
}

Write-Host ""
Write-Host "--- Check VMware version ---"
try {
    $vmwarePath = "C:\Program Files\VMware\VMware Workstation"
    if (Test-Path "$vmwarePath\vmware.exe") {
        $version = (Get-Item "$vmwarePath\vmware.exe").VersionInfo.FileVersion
        Write-Host "VMware version: $version"
        if ($version -lt "16.0.0") {
            Write-Host "WARNING: VMware < 16 doesn't support WHP. Upgrade to VMware 16+ or 17+"
        } else {
            Write-Host "VMware version supports WHP coexistence"
        }
    }
} catch {
    Write-Host "Could not determine VMware version"
}

Write-Host ""
Write-Host "--- Check if hypervisorlaunchtype is configured ---"
bcdedit /enum {current} 2>&1 | Select-String "hypervisorlaunchtype"
Write-Host ""

Write-Host "--- What this changes ---"
Write-Host "Before: WSL2(Hyper-V) XOR VMware → conflict → crash"
Write-Host "After:  WSL2(Hyper-V) AND VMware coexist via WHP"
Write-Host ""

Write-Host "After reboot:"
Write-Host "  1. Open VMware - should now show 'VMware Workstation is using"
Write-Host "     the Windows Hypervisor Platform (WHP)'"
Write-Host "  2. Start WSL2 - should work simultaneously with VMware"
Write-Host "  3. No more Hyper-V Event 167 crashes"

Write-Host ""
Write-Host "============================================"
Write-Host "  REBOOT REQUIRED"
Write-Host "============================================"
Read-Host
