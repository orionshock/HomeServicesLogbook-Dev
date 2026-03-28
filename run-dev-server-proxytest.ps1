# Activate the existing virtual environment

$venvActivateScript = ".\.venv\Scripts\Activate.ps1"

if (-not (Test-Path $venvActivateScript)) {
Write-Host "Virtual environment activation script not found at $venvActivateScript"
exit 1
}

. $venvActivateScript

# Local development environment variables (current session only)

$env:ALLOW_ACTOR_OVERRIDE = "false"
$env:APP_DATA_DIR = ".\data"

# New header-related env vars

$env:USE_UPSTREAM_AUTH = "true"
$env:UPSTREAM_ACTOR_HEADER = "X-Remote-User"
$env:USE_UPSTREAM_ROOT_PATH = "true"
$env:UPSTREAM_ROOT_PATH_HEADER = "X-Ingress-Path"

# Optional: if you want to test static root-path mode instead, set this and disable USE_UPSTREAM_ROOT_PATH

# $env:APP_ROOT_PATH = "/staticprefix"

# Launch the FastAPI development server

python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
