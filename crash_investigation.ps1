
Write-Host "============================================"
Write-Host "  CRASH SCENE INVESTIGATION"
Write-Host "============================================"

Write-Host ""
Write-Host "--- 1. Find all unexpected shutdowns (Event 41) ---"
$shutdowns = Get-WinEvent -FilterHashtable @{LogName='System'; Id=41} -MaxEvents 20 -ErrorAction SilentlyContinue
Write-Host "Total forced shutdowns found: $($shutdowns.Count)"
$shutdownTimes = @()
foreach ($e in $shutdowns) {
    $shutdownTimes += $e.TimeCreated
    Write-Host "  $($e.TimeCreated)"
}

Write-Host ""
Write-Host "--- 2. What happened 5 minutes BEFORE each crash? ---"
foreach ($st in $shutdownTimes | Select-Object -First 5) {
    $before = $st.AddMinutes(-5)
    Write-Host ""
    Write-Host "=== Crash at $st ==="
    Write-Host "Events from $before to $st :"

    $events = Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$before; EndTime=$st} -MaxEvents 50 -ErrorAction SilentlyContinue
    $errors = $events | Where-Object { $PSItem.Level -le 3 }
    Write-Host "  Total events in 5min window: $($events.Count)"
    Write-Host "  Errors/Warnings: $($errors.Count)"

    if ($errors.Count -gt 0) {
        Write-Host ""
        Write-Host "  Key events before crash:"
        $errors | Select-Object -First 15 TimeCreated, LevelDisplayName, ProviderName, Id, @{N='Detail';E={($PSItem.Message -replace "`n"," ").Substring(0, [Math]::Min(200, $PSItem.Message.Length))}} | Format-Table -AutoSize -Wrap
    }
}

Write-Host ""
Write-Host "--- 3. Check for crash dumps and WER reports ---"
$dumpPaths = @(
    "C:\Windows\Minidump",
    "C:\Windows\MEMORY.DMP",
    "C:\Windows\LiveKernelReports"
)
foreach ($p in $dumpPaths) {
    if (Test-Path $p) {
        $files = Get-ChildItem $p -Recurse -ErrorAction SilentlyContinue
        Write-Host "$p : $($files.Count) files"
        if ($files.Count -gt 0 -and $files.Count -lt 20) {
            $files | Select-Object Name, LastWriteTime | Format-Table -AutoSize
        }
    } else {
        Write-Host "$p : NOT FOUND"
    }
}

Write-Host ""
Write-Host "--- 4. Check Application events near crashes ---"
foreach ($st in $shutdownTimes | Select-Object -First 3) {
    $before = $st.AddMinutes(-3)
    Write-Host ""
    Write-Host "--- App events before $st ---"
    $appHangs = Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=$before; EndTime=$st; Id=1002} -MaxEvents 10 -ErrorAction SilentlyContinue
    if ($appHangs) {
        foreach ($a in $appHangs) {
            if ($a.Message -match '程序 (.+?) 版本') {
                Write-Host "  APP HANG: $($Matches[1]) at $($a.TimeCreated)"
            }
        }
    }
    $appErrors = Get-WinEvent -FilterHashtable @{LogName='Application'; Level=1,2; StartTime=$before; EndTime=$st} -MaxEvents 10 -ErrorAction SilentlyContinue
    if ($appErrors) {
        foreach ($a in $appErrors) {
            Write-Host "  APP ERROR: $($a.ProviderName) Id=$($a.Id) at $($a.TimeCreated)"
        }
    }
}

Write-Host ""
Write-Host "--- 5. Windows Reliability Monitor ---"
try {
    $reliability = Get-CimInstance -ClassName Win32_ReliabilityRecords -ErrorAction SilentlyContinue
    $critical = $reliability | Where-Object { $PSItem.EventIdentifier -in @(1001,1002,41,6008) } | Select-Object -First 10
    if ($critical) {
        Write-Host "Recent critical reliability events:"
        foreach ($r in $critical) {
            $time = [DateTime]::FromFileTime($r.TimeGenerated)
            Write-Host "  $time - EventId=$($r.EventIdentifier) - $($r.ProductName) - $($r.SourceName)"
        }
    } else {
        Write-Host "No critical reliability events found"
    }
} catch {
    Write-Host "Reliability monitor not accessible"
}

Write-Host ""
Write-Host "--- 6. Check for WHEA (hardware) errors ---"
$wheaErrors = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'} -MaxEvents 10 -ErrorAction SilentlyContinue
Write-Host "WHEA hardware errors: $($wheaErrors.Count)"
if ($wheaErrors.Count -gt 0) {
    foreach ($w in $wheaErrors) {
        Write-Host "  $($w.TimeCreated) - Id=$($w.Id)"
    }
}

Write-Host ""
Write-Host "--- 7. Check for disk reset/timeout events ---"
$diskTimeouts = Get-WinEvent -FilterHashtable @{LogName='System'; Id=@(129,153,11,51); Level=1,2,3} -MaxEvents 30 -ErrorAction SilentlyContinue
Write-Host "Disk timeouts/resets: $($diskTimeouts.Count)"
if ($diskTimeouts.Count -gt 0) {
    $diskTimeouts | Select-Object -First 10 TimeCreated, Id, LevelDisplayName, ProviderName, @{N='Short';E={($PSItem.Message -split "`n")[0]}} | Format-Table -AutoSize
}

Read-Host
