
Write-Host "============================================"
Write-Host "  INTEL DRIVER UPDATE SCRIPT"
Write-Host "============================================"

Write-Host ""
Write-Host "Step 1: Search Windows Update for driver updates..."

$driverUpdates = @()
try {
    $session = New-Object -ComObject Microsoft.Update.Session
    $searcher = $session.CreateUpdateSearcher()
    $results = $searcher.Search("IsInstalled=0 AND Type='Driver'")

    foreach ($update in $results.Updates) {
        $driverUpdates += $update
        Write-Host "  Found: $($update.Title)"
    }
    Write-Host "  Total driver updates: $($driverUpdates.Count)"
} catch {
    Write-Host "  Windows Update COM search failed: $_"
}

Write-Host ""
Write-Host "Step 2: Check current Intel drivers..."
$gpu = Get-CimInstance Win32_VideoController | Where-Object { $PSItem.Name -match 'Intel' }
if ($gpu) {
    Write-Host "  GPU: $($gpu.Name)"
    Write-Host "  Version: $($gpu.DriverVersion)"
    Write-Host "  Date: $($gpu.DriverDate)"
}

Write-Host ""
Write-Host "Step 3: Check Intel Chipset drivers..."
$chipsetDrivers = @('iaLPSS2_GPIO2_CNL','iaLPSS2_I2C_CNL','iaLPSS2_SPI_CNL','iaLPSS2_UART2_CNL','MEIx64','intelppm')
foreach ($drv in $chipsetDrivers) {
    $info = Get-CimInstance Win32_PnPSignedDriver | Where-Object { $PSItem.DeviceName -match $drv } | Select-Object -First 1
    if ($info) {
        Write-Host "  $drv : $($info.DriverVersion) ($($info.DriverDate))"
    }
}

Write-Host ""
Write-Host "Step 4: Download Intel Driver & Support Assistant..."
$dsaUrl = "https://downloadmirror.intel.com/28425/Intel-Driver-and-Support-Assistant-Installer.exe"
$outPath = "$env:TEMP\Intel-DSA-Installer.exe"

try {
    Write-Host "  Downloading from Intel..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $dsaUrl -OutFile $outPath -ErrorAction Stop -TimeoutSec 30
    Write-Host "  Downloaded to: $outPath"
    Write-Host ""
    Write-Host "  Launching Intel DSA installer..."
    Start-Process -FilePath $outPath -ArgumentList "/silent /norestart" -Wait -ErrorAction SilentlyContinue
    Write-Host "  Installer launched"
} catch {
    Write-Host "  Download failed: $_"
    Write-Host "  Will try alternative methods..."
}

Write-Host ""
Write-Host "Step 5: Try Windows Update API to install drivers..."
if ($driverUpdates.Count -gt 0) {
    try {
        $downloader = $session.CreateUpdateDownloader()
        $downloader.Updates = $driverUpdates
        Write-Host "  Downloading $($driverUpdates.Count) driver updates..."
        $downloadResult = $downloader.Download()
        Write-Host "  Download result: $($downloadResult.ResultCode)"

        $installer = $session.CreateUpdateInstaller()
        $installer.Updates = $driverUpdates
        Write-Host "  Installing..."
        $installResult = $installer.Install()
        Write-Host "  Install result: $($installResult.ResultCode)"
    } catch {
        Write-Host "  WU install failed: $_"
    }
} else {
    Write-Host "  No driver updates found via WU"
}

Write-Host ""
Write-Host "Step 6: Check for driver updates via Settings API..."
try {
    $updateSession = New-Object -ComObject 'Microsoft.Update.Session'
    $updateSearcher = $updateSession.CreateUpdateSearcher()
    $searchResult = $updateSearcher.Search("IsInstalled=0")
    Write-Host "  Total pending updates: $($searchResult.Updates.Count)"

    $intelDrivers = $searchResult.Updates | Where-Object {
        $PSItem.Title -match 'Intel|Graphic|Display|Conexant|Audio|Chipset|Serial.IO|Sensor|Firmware|BIOS|System'
    }
    if ($intelDrivers) {
        foreach ($d in $intelDrivers) {
            Write-Host "  DRIVER CANDIDATE: $($d.Title)"
        }
    }
} catch {
    Write-Host "  Settings API failed: $_"
}

Write-Host ""
Write-Host "============================================"
Write-Host "  Press Enter to exit..."
Read-Host
