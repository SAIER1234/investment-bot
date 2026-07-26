
Write-Host "=== RENAMING KASPERSKY DRIVER FILES ==="
Write-Host "This will prevent them from loading on next boot."
Write-Host ""

$klPaths = @(
    "C:\Windows\system32\DRIVERS\K4W-21-25\klbackupdisk.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\klbackupflt.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\kldisk.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\klflt.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\klgse.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\klhk.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\klif.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\klkbdflt.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\klmouflt.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\klpd.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\klpnpflt.sys",
    "C:\Windows\system32\DRIVERS\K4W-21-25\klwtp.sys",
    "C:\Windows\system32\DRIVERS\klim6.sys",
    "C:\ProgramData\Kaspersky Lab\AVP21.25\Bases\klids.sys",
    "C:\Windows\system32\Drivers\klupd_K4W-21-25_arkmon.sys",
    "C:\Windows\system32\Drivers\klupd_K4W-21-25_klbg.sys"
)

$renamed = 0
foreach ($path in $klPaths) {
    if (Test-Path $path) {
        $newPath = $path + ".disabled"
        try {
            # Take ownership first
            takeown /f $path 2>&1 | Out-Null
            icacls $path /grant "Administrators:F" 2>&1 | Out-Null

            # Rename
            Rename-Item -Path $path -NewName (Split-Path $path -Leaf) + ".disabled" -Force -ErrorAction Stop
            Write-Host "  RENAMED: $path -> $newPath"
            $renamed++
        } catch {
            Write-Host "  FAILED to rename: $path - $_"
            # Try Move-Item as backup
            try {
                Move-Item -Path $path -Destination $newPath -Force -ErrorAction Stop
                Write-Host "  MOVED: $path -> $newPath"
                $renamed++
            } catch {
                Write-Host "  MOVE also failed"
            }
        }
    } else {
        Write-Host "  NOT FOUND: $path"
    }
}

Write-Host ""
Write-Host "Renamed: $renamed / $($klPaths.Count)"
Write-Host ""
Write-Host "After reboot, these drivers will fail to load."
Write-Host "The 17 currently-loaded instances in memory will be gone."
Write-Host ""
Write-Host "Estimated nonpaged pool saved: ~300-500 MB"

Read-Host
