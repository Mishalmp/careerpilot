# Stops the CareerPilot API (port 8010) and web app (port 3100), including the helper processes that
# uvicorn --reload leaves behind. Only processes tied to those two ports or to the CareerPilot
# launch command are touched; other Python or Node programs are left alone.
$ErrorActionPreference = 'SilentlyContinue'
$all = Get-CimInstance Win32_Process
$kill = New-Object 'System.Collections.Generic.HashSet[int]'

# 1. Whatever listens on the two ports (the process may already be gone: its children still hold the socket).
foreach ($port in 8010, 3100) {
    Get-NetTCPConnection -LocalPort $port -State Listen | ForEach-Object { [void]$kill.Add([int]$_.OwningProcess) }
}
# 2. The launcher windows and the uvicorn command itself.
$all | Where-Object { $_.CommandLine -match 'careerpilot\.main:app_factory' } | ForEach-Object { [void]$kill.Add([int]$_.ProcessId) }

# 3. Children of those: real children, and uvicorn's spawned worker, which names its parent in its command line.
do {
    $before = $kill.Count
    foreach ($p in $all) {
        if ($kill.Contains([int]$p.ParentProcessId)) { [void]$kill.Add([int]$p.ProcessId) }
        if ($p.CommandLine -match 'spawn_main\(parent_pid=(\d+)' -and $kill.Contains([int]$Matches[1])) { [void]$kill.Add([int]$p.ProcessId) }
    }
} while ($kill.Count -gt $before)

$kill.Remove($PID) | Out-Null
foreach ($id in $kill) {
    $name = ($all | Where-Object { $_.ProcessId -eq $id }).Name
    if ($name) { & taskkill /PID $id /T /F | Out-Null; Write-Host ("  stopped {0} (pid {1})" -f $name, $id) }
}
if ($kill.Count -eq 0) { Write-Host '  nothing was running on ports 8010 or 3100' }
