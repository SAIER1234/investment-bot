
Write-Host "============================================"
Write-Host "  E: DRIVE COMPREHENSIVE DIAGNOSTIC"
Write-Host "============================================"

Write-Host ""
Write-Host "--- 1. Is E: drive marked as dirty? ---"
$isDirty = chkntfs E: 2>&1
Write-Host $isDirty

Write-Host ""
Write-Host "--- 2. E: drive filesystem info ---"
$vol = Get-Volume -DriveLetter E -ErrorAction SilentlyContinue
if ($vol) {
    Write-Host "FileSystem: $($vol.FileSystem)"
    Write-Host "FileSystemLabel: $($vol.FileSystemLabel)"
    Write-Host "HealthStatus: $($vol.HealthStatus)"
    Write-Host "OperationalStatus: $($vol.OperationalStatus)"
    Write-Host "Size: $([math]::Round($vol.Size/1GB,1)) GB"
    Write-Host "SizeRemaining: $([math]::Round($vol.SizeRemaining/1GB,1)) GB"
}

Write-Host ""
Write-Host "--- 3. Physical disk health ---"
$disk = Get-PhysicalDisk | Where-Object { $PSItem.FriendlyName -like '*Passport*' }
if ($disk) {
    Write-Host "Model: $($disk.FriendlyName)"
    Write-Host "HealthStatus: $($disk.HealthStatus)"
    Write-Host "OperationalStatus: $($disk.OperationalStatus)"
    Write-Host "MediaType: $($disk.MediaType)"
    Write-Host "BusType: $($disk.BusType)"
    Write-Host "Size: $([math]::Round($disk.Size/1GB,1)) GB"

    Write-Host ""
    Write-Host "--- 4. SMART / Reliability counters ---"
    try {
        $smart = Get-PhysicalDisk -SerialNumber $disk.SerialNumber | Get-StorageReliabilityCounter
        Write-Host "ReadErrorsTotal: $($smart.ReadErrorsTotal)"
        Write-Host "ReadErrorsCorrected: $($smart.ReadErrorsCorrected)"
        Write-Host "ReadErrorsUncorrected: $($smart.ReadErrorsUncorrected)"
        Write-Host "WriteErrorsTotal: $($smart.WriteErrorsTotal)"
        Write-Host "WriteErrorsCorrected: $($smart.WriteErrorsCorrected)"
        Write-Host "WriteErrorsUncorrected: $($smart.WriteErrorsUncorrected)"
        Write-Host "PowerOnHours: $($smart.PowerOnHours)"
        Write-Host "Temperature: $($smart.Temperature)"
        Write-Host "Wear: $($smart.Wear)"
    } catch {
        Write-Host "SMART data not available via this method"
        Write-Host "Trying alternative..."
        try {
            $smart2 = Get-CimInstance -Namespace root/wmi -ClassName MSStorageDriver_ATAPISmartData -ErrorAction Stop
            Write-Host "Got SMART data via WMI"
        } catch {
            Write-Host "USB drives do not expose SMART via WMI on Windows"
        }
    }
}

Write-Host ""
Write-Host "--- 5. Recent disk controller errors for Harddisk1 ---"
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$diskErrors = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='disk'; StartTime=$bootTime} -MaxEvents 20 -ErrorAction SilentlyContinue
Write-Host "Disk errors since boot: $($diskErrors.Count)"
foreach ($e in $diskErrors) {
    if ($e.Message -match 'Harddisk1') {
        Write-Host "  Harddisk1 error found!"
        Write-Host "  Time: $($e.TimeCreated)"
        Write-Host "  ID: $($e.Id)"
        Write-Host "  Level: $($e.LevelDisplayName)"
    }
}

Write-Host ""
Write-Host "--- 6. Check for pending chkdsk ---"
$dirtyCheck = fsutil dirty query E: 2>&1
Write-Host $dirtyCheck

Write-Host ""
Write-Host "--- 7. USB device status for the external drive ---"
$usbDevices = Get-PnpDevice -Class DiskDrive -ErrorAction SilentlyContinue | Where-Object { $PSItem.FriendlyName -match 'Passport|WD' }
foreach ($dev in $usbDevices) {
    Write-Host "Device: $($dev.FriendlyName)"
    Write-Host "Status: $($dev.Status)"
    Write-Host "InstanceId: $($dev.InstanceId)"
}

Write-Host ""
Write-Host "--- 8. USB Root Hub status ---"
$usbHubs = Get-PnpDevice -Class USB -ErrorAction SilentlyContinue | Where-Object { $PSItem.Status -ne 'OK' }
if ($usbHubs) {
    Write-Host "Problem USB devices:"
    $usbHubs | Format-Table FriendlyName, Status -AutoSize
} else {
    Write-Host "All USB devices OK"
}

Write-Host ""
Write-Host "--- 9. Kaspersky drivers check ---"
$klDrivers = Get-CimInstance Win32_SystemDriver | Where-Object { $PSItem.Name -like 'kl*' -and $PSItem.State -eq 'Running' }
Write-Host "Running Kaspersky drivers: $($klDrivers.Count)"
if ($klDrivers.Count -gt 0) {
    foreach ($d in $klDrivers) { Write-Host "  - $($d.Name)" }
} else {
    Write-Host "  ALL GONE! Kaspersky uninstall was successful."
}

Read-Host
