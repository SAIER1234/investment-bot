
Write-Host "=== Finding what launches esrv.exe ==="

Write-Host ""
Write-Host "--- Scheduled Tasks ---"
schtasks /query /fo LIST /v 2>$null | Select-String -Pattern 'esrv|SUR|QUEENCREEK|Intel.*SUR' -Context 1,0 | Select-Object -First 10

Write-Host ""
Write-Host "--- Looking in Task Scheduler folders ---"
$folders = @('\Intel','\Intel\SUR','\OEM','\OEM\Intel')
foreach ($folder in $folders) {
    try {
        $tasks = Get-ScheduledTask -TaskPath "$folder\" -ErrorAction Stop
        foreach ($task in $tasks) {
            Write-Host "Found: $folder$($task.TaskName)"
            Write-Host "  State: $($task.State)"
            $action = $task.Actions | Select-Object -First 1
            Write-Host "  Action: $($action.Execute) $($action.Arguments)"
        }
    } catch {
        # Folder doesn't exist, skip
    }
}

Write-Host ""
Write-Host "--- Check service triggers that might launch SUR ==="
$surSvc = Get-Service -Name 'SystemUsageReportSvc_QUEENCREEK' -ErrorAction SilentlyContinue
if ($surSvc) {
    Write-Host "SystemUsageReportSvc: $($surSvc.Status) / $($surSvc.StartType)"
    Write-Host "Trigger info - need sc qtrigger:"
    sc.exe qtrigger SystemUsageReportSvc_QUEENCREEK 2>&1
}

Write-Host ""
Write-Host "--- Check Intel SUR folder contents ---"
if (Test-Path "C:\Program Files\Intel\SUR\QUEENCREEK\x64") {
    Get-ChildItem "C:\Program Files\Intel\SUR\QUEENCREEK\x64" -Filter "*.exe" | Select-Object Name
}
if (Test-Path "C:\Program Files\Intel\SUR\QUEENCREEK") {
    Get-ChildItem "C:\Program Files\Intel\SUR\QUEENCREEK" -Filter "*.xml" -ErrorAction SilentlyContinue | Select-Object Name
    Get-ChildItem "C:\Program Files\Intel\SUR\QUEENCREEK" -Filter "*.ini" -ErrorAction SilentlyContinue | Select-Object Name
}

Read-Host
