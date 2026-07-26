
Write-Host "=== Installing ALL pending Windows Updates (including firmware) ==="
Write-Host ""
Write-Host "Step 1: Searching for all pending updates..."
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$results = $searcher.Search("IsInstalled=0")
Write-Host "Found $($results.Updates.Count) pending updates:"
foreach ($update in $results.Updates) {
    Write-Host "  - $($update.Title)"
}

Write-Host ""
Write-Host "Step 2: Downloading updates..."
$downloader = $session.CreateUpdateDownloader()
$downloader.Updates = $results.Updates
$downloadResult = $downloader.Download()
Write-Host "Download: $($downloadResult.ResultCode) - $($downloadResult.HResult)"

Write-Host ""
Write-Host "Step 3: Installing updates..."
try {
    $installer = $session.CreateUpdateInstaller()
    $installer.Updates = $results.Updates
    $installResult = $installer.Install()
    Write-Host "Install: $($installResult.ResultCode)"
    Write-Host "Reboot required: $($installResult.RebootRequired)"
    if ($installResult.RebootRequired) {
        Write-Host "!!! REBOOT REQUIRED after updates !!!"
    }
} catch {
    Write-Host "Install error: $_"
    Write-Host "Trying individual install..."
    foreach ($update in $results.Updates) {
        try {
            if ($update.IsDownloaded) {
                $installer = $session.CreateUpdateInstaller()
                $installer.Updates = @($update)
                $result = $installer.Install()
                Write-Host "  $($update.Title): $($result.ResultCode)"
            }
        } catch {
            Write-Host "  $($update.Title): FAILED"
        }
    }
}

Write-Host ""
Write-Host "=== CRITICAL: Check BIOS/Firmware version ==="
Get-CimInstance Win32_BIOS | Select-Object Manufacturer, SMBIOSBIOSVersion, ReleaseDate | Format-List

Write-Host ""
Write-Host "Press Enter to exit..."
Read-Host
