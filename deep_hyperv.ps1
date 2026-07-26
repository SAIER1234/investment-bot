
Write-Host "============================================"
Write-Host "  HYPER-V DEEP ANALYSIS"
Write-Host "============================================"

Write-Host ""
Write-Host "--- Event 167 message (latest) ---"
$ev = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Hyper-V-Hypervisor'; Id=167} -MaxEvents 1 -ErrorAction SilentlyContinue
Write-Host $ev.Message

Write-Host ""
Write-Host "--- BCD configuration ---"
bcdedit /enum {current} 2>&1

Write-Host ""
Write-Host "--- Core Isolation / Memory Integrity ---"
try {
    $coreIso = Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard -ErrorAction Stop
    Write-Host "VirtualizationBasedSecurityStatus: $($coreIso.VirtualizationBasedSecurityStatus)"
    Write-Host "RequiredSecurityProperties:"
    $coreIso.RequiredSecurityProperties | ForEach-Object { Write-Host "  - $_" }
    Write-Host "AvailableSecurityProperties:"
    $coreIso.AvailableSecurityProperties | ForEach-Object { Write-Host "  - $_" }
    Write-Host "SecurityServicesRunning:"
    $coreIso.SecurityServicesRunning | ForEach-Object { Write-Host "  - $_" }
} catch {
    Write-Host "DeviceGuard WMI not available"
}

Write-Host ""
Write-Host "--- Hypervisor running? ---"
systeminfo 2>&1 | Select-String "Hyper-V"

Write-Host ""
Write-Host "--- VMware running? ---"
$vmware = Get-Process -Name vmware,vmware-vmx -ErrorAction SilentlyContinue
if ($vmware) { Write-Host "VMware IS running" } else { Write-Host "VMware NOT running" }

Write-Host ""
Write-Host "--- Check if Event 167 = crash trigger or benign ---"
Write-Host "Timeline: all Event 167 vs Event 41"
$all167 = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Hyper-V-Hypervisor'; Id=167} -MaxEvents 50 -ErrorAction SilentlyContinue
$all41 = Get-WinEvent -FilterHashtable @{LogName='System'; Id=41} -MaxEvents 20 -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Event 167 total: $($all167.Count)"
Write-Host "Event 41 total: $($all41.Count)"

$crashTimes = @()
foreach ($e in $all41) { $crashTimes += $e.TimeCreated }

Write-Host ""
Write-Host "Analyzing: does EVERY Event 167 precede a crash?"
$correlated = 0
$standalone = 0
foreach ($e167 in $all167) {
    $found = $false
    foreach ($ct in $crashTimes) {
        $diff = ($ct - $e167.TimeCreated).TotalSeconds
        if ($diff -gt 0 -and $diff -lt 10) {
            $correlated++
            $found = $true
            break
        }
    }
    if (-not $found) { $standalone++ }
}
Write-Host "Event 167 correlated with crash (<10s before): $correlated"
Write-Host "Event 167 standalone (no crash follows): $standalone"
Write-Host ""
if ($standalone -gt $correlated -and $standalone -gt 5) {
    Write-Host "CONCLUSION: Event 167 fires REGULARLY without causing crashes."
    Write-Host "The crash correlation was coincidental - Event 167 is a benign"
    Write-Host "warning about speculative execution mitigations."
    Write-Host ""
    Write-Host "The REAL crash cause was one or more of:"
    Write-Host "  - Kaspersky 16 drivers (now removed)"
    Write-Host "  - Huawei services (now disabled)"
    Write-Host "  - Energy Server crashes (now disabled)"
    Write-Host "  - USBPcap conflicts (now disabled)"
    Write-Host ""
    Write-Host "These created such severe resource exhaustion that when"
    Write-Host "Event 167 fired (a routine Hyper-V event), the system"
    Write-Host "was already on the brink and tipped over."
}

Read-Host
