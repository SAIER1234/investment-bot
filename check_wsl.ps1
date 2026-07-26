
Write-Host "=== vmmemWSL Process ==="
$wsl = Get-Process -Name vmmemWSL -ErrorAction SilentlyContinue
if ($wsl) {
    $ws = [math]::Round($wsl.WorkingSet64/1MB, 1)
    $priv = [math]::Round($wsl.PrivateMemorySize64/1MB, 1)
    $vm = [math]::Round($wsl.VirtualMemorySize64/1MB, 1)
    $cpu = [math]::Round($wsl.CPU, 1)
    Write-Host "WorkingSet:   $ws MB"
    Write-Host "PrivateBytes: $priv MB"
    Write-Host "VirtualMem:   $vm MB"
    Write-Host "CPU Time:     $cpu sec"
    Write-Host "Threads:      $($wsl.Threads.Count)"
} else {
    Write-Host "vmmemWSL NOT running"
}

Write-Host ""
Write-Host "=== WSL Config ==="
Get-Content "$env:USERPROFILE\.wslconfig"

Write-Host ""
Write-Host "=== WSL Distros ==="
wsl --list --verbose

Write-Host ""
Write-Host "=== Your options ==="
Write-Host "1. wsl --shutdown     -> Stop WSL NOW, free memory immediately"
Write-Host "2. wsl --terminate Ubuntu -> Stop only Ubuntu"
Write-Host "3. Unregister Ubuntu  -> Delete WSL permanently"
Write-Host "4. Reduce memory limit -> Edit .wslconfig, set memory=2GB"

Write-Host ""
Write-Host "Press Enter..."
Read-Host
