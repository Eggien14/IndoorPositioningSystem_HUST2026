param(
	[int]$Port = 8000,
	[switch]$NoReload
)

# Start Indoor Positioning System Server
Write-Host "Starting Indoor Positioning System Server..." -ForegroundColor Green

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvActivatePath = Join-Path $projectRoot "venv\Scripts\Activate.ps1"

if (-not (Test-Path $venvActivatePath)) {
	Write-Host "Virtual environment not found: $venvActivatePath" -ForegroundColor Red
	Write-Host "Please create venv first. See READ_ME/Started/Env.md" -ForegroundColor Yellow
	exit 1
}

# Activate virtual environment
& $venvActivatePath

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
	Write-Host "Port $Port is already in use by PID(s): $($listener.OwningProcess -join ', ')" -ForegroundColor Red
	Write-Host "Run .\scripts\stop_server.ps1 first, then start again." -ForegroundColor Yellow
	exit 1
}

# Start server
Write-Host "Server will run on: http://localhost:$Port" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

Push-Location $projectRoot
try {
	if ($NoReload) {
		python -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
	} else {
		python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port $Port
	}
}
finally {
	Pop-Location
}
