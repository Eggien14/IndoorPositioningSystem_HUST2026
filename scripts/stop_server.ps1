param(
    [int]$Port = 8000
)

# Stop Indoor Positioning System server processes
Write-Host "Stopping Indoor Positioning System Server..." -ForegroundColor Yellow

function Get-DescendantProcessIds {
    param(
        [int[]]$ParentIds
    )

    $all = Get-CimInstance Win32_Process
    $descendants = New-Object System.Collections.Generic.List[int]
    $queue = New-Object System.Collections.Generic.Queue[int]

    foreach ($id in $ParentIds) {
        $queue.Enqueue($id)
    }

    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        $children = $all | Where-Object { $_.ParentProcessId -eq $current } | Select-Object -ExpandProperty ProcessId
        foreach ($child in $children) {
            if (-not $descendants.Contains([int]$child)) {
                $descendants.Add([int]$child)
                $queue.Enqueue([int]$child)
            }
        }
    }

    return $descendants
}

$listenerPids = @(
    Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
)

$uvicornPids = @(
    Get-CimInstance Win32_Process |
    Where-Object {
        ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and
        $_.CommandLine -like '*uvicorn*backend.main:app*'
    } |
    Select-Object -ExpandProperty ProcessId
)

$rootPids = @($listenerPids + $uvicornPids | Sort-Object -Unique)

if (-not $rootPids -or $rootPids.Count -eq 0) {
    Write-Host "No server process found on port $Port." -ForegroundColor Gray
    exit 0
}

$childPids = Get-DescendantProcessIds -ParentIds $rootPids
$allPidList = New-Object System.Collections.Generic.List[int]
foreach ($pidValue in $childPids) {
    if ($pidValue) {
        $allPidList.Add([int]$pidValue)
    }
}
foreach ($pidValue in $rootPids) {
    if ($pidValue) {
        $allPidList.Add([int]$pidValue)
    }
}
$allPidsToStop = @($allPidList | Sort-Object -Unique)

foreach ($procId in $allPidsToStop) {
    if ($procId -and $procId -ne $PID) {
        Write-Host "Stopping process ID: $procId" -ForegroundColor Red
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Milliseconds 400
$remaining = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "Port $Port is still in use. Run script again or stop manually." -ForegroundColor Yellow
    exit 1
}

Write-Host "Server stopped successfully!" -ForegroundColor Green
