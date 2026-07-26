
Write-Host "============================================"
Write-Host "  BLOAT REMOVAL"
Write-Host "============================================"

Write-Host ""
Write-Host "--- 1. Disable Huawei WUCSProxy service ---"
$wucs = Get-Service -Name WUCSProxy -ErrorAction SilentlyContinue
if ($wucs) {
    Stop-Service -Name WUCSProxy -Force -ErrorAction SilentlyContinue
    Set-Service -Name WUCSProxy -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Host "WUCSProxy: DISABLED (Huawei PC Manager proxy)"
} else { Write-Host "WUCSProxy: not found" }

Write-Host ""
Write-Host "--- 2. Disable USER_ESRV_SVC_QUEENCREEK scheduled task ---"
try {
    Disable-ScheduledTask -TaskName "USER_ESRV_SVC_QUEENCREEK" -ErrorAction Stop
    Write-Host "USER_ESRV_SVC_QUEENCREEK: DISABLED"
} catch {
    Unregister-ScheduledTask -TaskName "USER_ESRV_SVC_QUEENCREEK" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "USER_ESRV_SVC_QUEENCREEK: UNREGISTERED"
}

Write-Host ""
Write-Host "--- 3. Disable LaunchDouyinGuard scheduled task ---"
try {
    Disable-ScheduledTask -TaskName "LaunchDouyinGuard" -ErrorAction Stop
    Write-Host "LaunchDouyinGuard: DISABLED"
} catch {
    Unregister-ScheduledTask -TaskName "LaunchDouyinGuard" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "LaunchDouyinGuard: UNREGISTERED"
}

Write-Host ""
Write-Host "--- 4. Disable MiniTool ShadowMaker auto tasks ---"
Get-ScheduledTask -TaskName "*MiniTool*" -ErrorAction SilentlyContinue | ForEach-Object {
    Disable-ScheduledTask -TaskName $PSItem.TaskName -ErrorAction SilentlyContinue
    Write-Host "Disabled: $($PSItem.TaskName)"
}

Write-Host ""
Write-Host "--- 5. Disable unnecessary updater tasks ---"
$updaterTasks = @(
    "QQBrowser Updater Task",
    "QQBrowser Updater Task(Core)",
    "360ZipUpdater",
    "360ZipUpdaterLoop",
    "Git for Windows Updater",
    "GoogleUpdaterTaskSystem152.0.7933.0{BDE9D880-4CB2-4188-BA5A-B5EF8DC2F936}",
    "QuarkUpdaterTaskUser1.0.0.21{71D72B6B-97DA-496F-AB23-D66F7C1381A5}",
    "npcapwatchdog"
)
foreach ($taskName in $updaterTasks) {
    try {
        Disable-ScheduledTask -TaskName $taskName -ErrorAction Stop
        Write-Host "Disabled: $taskName"
    } catch {
        # Task might have different name format
    }
}

Write-Host ""
Write-Host "--- 6. Disable Intel Collector/Telemetry ---"
$intelSvc = @('IntelCollectorService', 'IntelTelemetryAgent', 'dptftcs')
foreach ($name in $intelSvc) {
    try {
        Set-Service -Name $name -StartupType Manual -ErrorAction Stop
        Stop-Service -Name $name -Force -ErrorAction SilentlyContinue
        Write-Host "$name : Manual"
    } catch {
        Write-Host "$name : not found or access denied"
    }
}

Write-Host ""
Write-Host "--- 7. Check webthreatdefusersvc status ---"
$wt = Get-Service -Name webthreatdefusersvc_8f163 -ErrorAction SilentlyContinue
if ($wt) {
    Write-Host "webthreatdefusersvc: $($wt.Status) / $($wt.StartType)"
    Write-Host "  Display: $($wt.DisplayName)"
    Write-Host "  (This may be Kaspersky remnant - check if needed)"
}

Write-Host ""
Write-Host "--- 8. CURRENT STATUS ---"
Write-Host "Active scheduled tasks (non-MS):"
(Get-ScheduledTask | Where-Object { $PSItem.TaskPath -notmatch 'Microsoft' -and $PSItem.State -ne 'Disabled' } | Measure-Object).Count

Write-Host ""
Write-Host "--- 9. EDGE MEMORY ANALYSIS ---"
$edge = Get-Process -Name msedge -ErrorAction SilentlyContinue
$totalEdgeWS = [math]::Round(($edge | Measure-Object -Property WorkingSet64 -Sum).Sum/1MB, 1)
$totalEdgePriv = [math]::Round(($edge | Measure-Object -Property PrivateMemorySize64 -Sum).Sum/1MB, 1)
Write-Host "Edge processes: $($edge.Count)"
Write-Host "Edge WorkingSet: $totalEdgeWS MB"
Write-Host "Edge PrivateBytes: $totalEdgePriv MB"
Write-Host ""
Write-Host "RECOMMENDATION:"
Write-Host "  1. Close unused tabs (each tab = ~150 MB)"
Write-Host "  2. edge://settings/system -> Enable 'Sleeping tabs'"
Write-Host "  3. edge://settings/system -> Enable 'Efficiency mode'"

Write-Host ""
Write-Host "--- 10. OVERALL MEMORY ---"
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "Free: $([math]::Round($os.FreePhysicalMemory/1MB,1)) GB"
Write-Host "If Edge memory drops by 2GB (close 10-15 tabs), system will be at ~4GB free"

Read-Host
