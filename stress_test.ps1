
Write-Host "============================================"
Write-Host "  SYSTEM STRESS TEST SUITE"
Write-Host "  Start: $(Get-Date)"
Write-Host "============================================"

# --- BASELINE ---
Write-Host ""
Write-Host "========== TEST 1: BASELINE =========="
$os = Get-CimInstance Win32_OperatingSystem
$mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
$baseline = @{
    FreeMem = [math]::Round($os.FreePhysicalMemory/1MB, 1)
    TotalMem = [math]::Round($os.TotalVisibleMemorySize/1MB, 1)
    NonpagedPool = [math]::Round($mem.PoolNonpagedBytes/1MB, 1)
    PagedPool = [math]::Round($mem.PoolPagedBytes/1MB, 1)
}
Write-Host "Memory: $($baseline.FreeMem) GB free / $($baseline.TotalMem) GB"
Write-Host "Nonpaged pool: $($baseline.NonpagedPool) MB"
Write-Host "Paged pool: $($baseline.PagedPool) MB"

$errorsBefore = (Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=(Get-Date).AddHours(-1)} -MaxEvents 100 -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "Errors in last hour: $errorsBefore"

$npHistory = @()
$npHistory += @{Time=Get-Date; NP=$baseline.NonpagedPool; FreeMem=$baseline.FreeMem}

Write-Host "BASELINE RECORDED"

# --- TEST 2: DISK I/O STRESS ---
Write-Host ""
Write-Host "========== TEST 2: DISK I/O STRESS =========="
Write-Host "Running sequential then random writes on C: drive..."
Write-Host "Creating 500MB test file..."
$testFile = "$env:TEMP\disk_stress_test.tmp"
try {
    # Sequential write
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $buffer = New-Object byte[] (100MB)
    (New-Object Random).NextBytes($buffer)
    [System.IO.File]::WriteAllBytes($testFile, $buffer)
    $sw.Stop()
    Write-Host "100MB sequential write: $($sw.ElapsedMilliseconds) ms"

    # Random read
    $sw.Restart()
    $allBytes = [System.IO.File]::ReadAllBytes($testFile)
    $sw.Stop()
    Write-Host "100MB sequential read: $($sw.ElapsedMilliseconds) ms"

    # Small random I/O
    $sw.Restart()
    $rng = New-Object Random
    for ($i = 0; $i -lt 1000; $i++) {
        $pos = $rng.Next(0, $allBytes.Length - 4096)
        $chunk = New-Object byte[] 4096
        [Array]::Copy($allBytes, $pos, $chunk, 0, 4096)
    }
    $sw.Stop()
    Write-Host "1000x 4KB random reads: $($sw.ElapsedMilliseconds) ms"

    Remove-Item $testFile -Force
    Write-Host "Test file cleaned"
} catch {
    Write-Host "DISK TEST ERROR: $_"
}

$npNow = [math]::Round((Get-CimInstance Win32_PerfRawData_PerfOS_Memory).PoolNonpagedBytes/1MB, 1)
$osNow = Get-CimInstance Win32_OperatingSystem
$npHistory += @{Time=Get-Date; NP=$npNow; FreeMem=[math]::Round($osNow.FreePhysicalMemory/1MB,1)}
Write-Host "Nonpaged pool after disk test: $npNow MB"
Write-Host "DISK TEST COMPLETE"

# --- TEST 3: BACKGROUND CPU+IO LOAD ---
Write-Host ""
Write-Host "========== TEST 3: BACKGROUND LOAD =========="
Write-Host "Spawning background load processes..."

# Start a CPU stress in background (30 seconds)
$cpuJob = Start-Job -ScriptBlock {
    $end = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $end) {
        $x = 0; for ($i = 0; $i -lt 1000000; $i++) { $x += $i * $i % 997 }
    }
}
Write-Host "CPU stress job started (PID: $($cpuJob.Id)) - 30 seconds"

# While CPU is loaded, do more I/O
Write-Host "Running mixed I/O during CPU load..."
$testFile2 = "$env:TEMP\mixed_stress.tmp"
try {
    for ($j = 0; $j -lt 5; $j++) {
        $buf = New-Object byte[] (50MB)
        (New-Object Random).NextBytes($buf)
        [System.IO.File]::WriteAllBytes($testFile2, $buf)
        $readback = [System.IO.File]::ReadAllBytes($testFile2)
    }
    Remove-Item $testFile2 -Force
} catch { Write-Host "Mixed IO error: $_" }

# Wait for CPU job
Wait-Job $cpuJob -Timeout 60 | Out-Null
Write-Host "CPU stress completed"

$npNow = [math]::Round((Get-CimInstance Win32_PerfRawData_PerfOS_Memory).PoolNonpagedBytes/1MB, 1)
$osNow = Get-CimInstance Win32_OperatingSystem
$npHistory += @{Time=Get-Date; NP=$npNow; FreeMem=[math]::Round($osNow.FreePhysicalMemory/1MB,1)}
Write-Host "Nonpaged pool after CPU+IO test: $npNow MB"
Write-Host "LOAD TEST COMPLETE"

# --- TEST 4: MEMORY ALLOCATION STRESS ---
Write-Host ""
Write-Host "========== TEST 4: MEMORY ALLOCATION STRESS =========="
Write-Host "Allocating and releasing large memory blocks..."

$allocated = @()
try {
    for ($k = 0; $k -lt 20; $k++) {
        $allocated += New-Object byte[] (200MB)
        Write-Host "  Allocated $($k+1) x 200MB = $(($k+1)*200) MB"
        Start-Sleep -Milliseconds 200
    }
    Write-Host "Total allocated: 4 GB"
    Start-Sleep -Seconds 2
    Write-Host "Releasing..."
    $allocated = $null
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
    Write-Host "Memory released"
} catch {
    Write-Host "Memory test hit limit: $_"
}

$npNow = [math]::Round((Get-CimInstance Win32_PerfRawData_PerfOS_Memory).PoolNonpagedBytes/1MB, 1)
$osNow = Get-CimInstance Win32_OperatingSystem
$npHistory += @{Time=Get-Date; NP=$npNow; FreeMem=[math]::Round($osNow.FreePhysicalMemory/1MB,1)}
Write-Host "Nonpaged pool after memory test: $npNow MB"
Write-Host "MEMORY TEST COMPLETE"

# --- FINAL ANALYSIS ---
Write-Host ""
Write-Host "============================================"
Write-Host "  STRESS TEST RESULTS"
Write-Host "============================================"

Write-Host ""
Write-Host "--- Nonpaged Pool Timeline ---"
foreach ($entry in $npHistory) {
    Write-Host ("  $($entry.Time.ToString('HH:mm:ss'))  NP: $($entry.NP) MB  FreeMem: $($entry.FreeMem) GB")
}

Write-Host ""
Write-Host "--- Growth Analysis ---"
$npStart = $npHistory[0].NP
$npEnd = $npHistory[-1].NP
$npDelta = [math]::Round($npEnd - $npStart, 1)
Write-Host "Nonpaged pool start: $npStart MB"
Write-Host "Nonpaged pool end: $npEnd MB"
Write-Host "Delta: $npDelta MB"

Write-Host ""
Write-Host "--- Memory Final ---"
$finalOs = Get-CimInstance Win32_OperatingSystem
$finalFree = [math]::Round($finalOs.FreePhysicalMemory/1MB, 1)
Write-Host "Final free memory: $finalFree GB"
Write-Host "Initial free memory: $($baseline.FreeMem) GB"

Write-Host ""
Write-Host "--- Errors During Test ---"
$testStartTime = $npHistory[0].Time
$errorsAfter = Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=$testStartTime} -MaxEvents 100 -ErrorAction SilentlyContinue
Write-Host "New errors during test: $($errorsAfter.Count)"
if ($errorsAfter.Count -gt 0) {
    $errorsAfter | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 5 Count, Name | Format-Table -AutoSize
}

Write-Host ""
Write-Host "--- VERDICT ---"
$allPassed = $true
if ($npDelta -gt 100) { Write-Host "FAIL: Nonpaged pool grew $npDelta MB (>100 MB) - possible leak"; $allPassed = $false }
elseif ($npDelta -gt 50) { Write-Host "WARN: Nonpaged pool grew $npDelta MB (>50 MB) - monitor"; $allPassed = $false }
else { Write-Host "PASS: Nonpaged pool stable ($npDelta MB growth)" }

if ($errorsAfter.Count -gt 0) { Write-Host "WARN: $($errorsAfter.Count) errors during test"; $allPassed = $false }
else { Write-Host "PASS: Zero errors during test" }

if ($finalFree -lt 1) { Write-Host "FAIL: Memory critically low ($finalFree GB)"; $allPassed = $false }
elseif ($finalFree -lt 2) { Write-Host "WARN: Memory low ($finalFree GB)"; $allPassed = $false }
else { Write-Host "PASS: Memory adequate ($finalFree GB free)" }

if ($allPassed) {
    Write-Host ""
    Write-Host "*** ALL TESTS PASSED - SYSTEM IS STABLE ***"
} else {
    Write-Host ""
    Write-Host "*** SOME TESTS FAILED - SEE ABOVE ***"
}

Write-Host ""
Write-Host "============================================"
