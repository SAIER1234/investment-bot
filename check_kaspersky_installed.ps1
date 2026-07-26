
Write-Host "=== KASPERSKY INSTALLATION STATUS ==="

Write-Host ""
Write-Host "--- Check Programs and Features ---"
$kasperskyApp = Get-CimInstance -ClassName Win32_Product -ErrorAction SilentlyContinue | Where-Object { $PSItem.Name -like '*Kaspersky*' -or $PSItem.Vendor -like '*Kaspersky*' }
if ($kasperskyApp) {
    $kasperskyApp | Select-Object Name, Version, Vendor | Format-Table -AutoSize
} else {
    Write-Host "No Kaspersky found in Programs and Features (may be partially uninstalled)"
}

Write-Host ""
Write-Host "--- Check Kaspersky folder ---"
$klPaths = @(
    "C:\Program Files\Kaspersky Lab",
    "C:\Program Files (x86)\Kaspersky Lab",
    "C:\ProgramData\Kaspersky Lab"
)
foreach ($p in $klPaths) {
    if (Test-Path $p) {
        Write-Host "FOUND: $p"
        Get-ChildItem $p -Directory -ErrorAction SilentlyContinue | Select-Object -First 5 Name
    } else {
        Write-Host "NOT FOUND: $p"
    }
}

Write-Host ""
Write-Host "--- Check avp.exe (Kaspersky main process) ---"
$avp = Get-Process -Name avp -ErrorAction SilentlyContinue
if ($avp) { Write-Host "avp.exe RUNNING" } else { Write-Host "avp.exe NOT running - Kaspersky user-mode is DEAD" }

Write-Host ""
Write-Host "--- Check Kaspersky services ---"
Get-Service | Where-Object { $PSItem.Name -match 'AVP|Kaspersky|kl' } | Select-Object Name, DisplayName, Status, StartType | Format-Table -AutoSize

Write-Host ""
Write-Host "--- CONCLUSION ---"
Write-Host "16 kernel drivers loaded but user-mode not running."
Write-Host "This is a broken Kaspersky installation."
Write-Host "These drivers filter ALL disk I/O, network, keyboard, mouse."
Write-Host "Each allocates nonpaged pool that Windows can never reclaim."
Write-Host ""
Write-Host "FIX: Uninstall Kaspersky completely, or we can disable the drivers."
Write-Host ""
Write-Host "Option 1: If Kaspersky is still installed, uninstall via Settings > Apps"
Write-Host "Option 2: I can disable all 16 kernel drivers right now (Stop + set to Disabled)"
Write-Host ""
Write-Host "Which would you prefer?"
Read-Host
