
Write-Host "=== Cleaning orphan driver registry entries ==="

$orphanKeys = @(
    'PRI-Driver',     # Huawei PC Manager orphan - .sys file missing
    'TxQBService'     # QQ Browser orphan - .exe file missing
)

foreach ($key in $orphanKeys) {
    $path = "HKLM:\SYSTEM\CurrentControlSet\Services\$key"
    if (Test-Path $path) {
        # Stop dependent services first
        sc.exe stop $key 2>$null

        # Disable the service
        Set-ItemProperty -Path $path -Name "Start" -Value 4 -Type DWord -Force -ErrorAction SilentlyContinue

        Write-Host "$key : registry entry cleaned (Start=Disabled)"
    } else {
        Write-Host "$key : not found (already cleaned?)"
    }
}

# Also check for other known orphans
$otherOrphans = @('HwEmuDrv')
foreach ($key in $otherOrphans) {
    $path = "HKLM:\SYSTEM\CurrentControlSet\Services\$key"
    if (Test-Path $path) {
        $img = (Get-ItemProperty -Path $path -ErrorAction SilentlyContinue).ImagePath
        if ($img) {
            $cleanPath = $img -replace '\\\\?\\?\\', ''
            $cleanPath = $cleanPath -replace 'SystemRoot', 'C:\Windows'
            $cleanPath = $cleanPath -replace '\\\\', '\\'
            if (-not (Test-Path $cleanPath)) {
                Write-Host "$key : ORPHAN - file missing: $cleanPath"
                Set-ItemProperty -Path $path -Name "Start" -Value 4 -Type DWord -Force -ErrorAction SilentlyContinue
                Write-Host "$key : set to Disabled"
            }
        }
    } else {
        Write-Host "$key : not found"
    }
}

Write-Host ""
Write-Host "=== Verifying startup service errors fixed ==="
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
