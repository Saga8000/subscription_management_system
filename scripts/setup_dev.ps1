<#
One-shot local setup (Windows replacement for a Makefile). Run from the project root:
    powershell -ExecutionPolicy Bypass -File scripts\setup_dev.ps1 [-Seed]

Prerequisite: .env exists (create it with scripts\create_database.ps1).
Steps: backend venv + pip install, Alembic upgrade on DATABASE_URL, optional demo seed, frontend npm install.
#>
param([switch]$Seed)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $root ".env"))) {
    throw ".env not found. Run scripts\create_database.ps1 first."
}

Push-Location (Join-Path $root "backend")
try {
    if (-not (Test-Path ".venv")) {
        Write-Host "Creating backend virtual environment..."
        py -3.11 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Could not create venv (Python 3.11+ required)." }
    }
    & .venv\Scripts\python -m pip install --disable-pip-version-check -q -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
    Write-Host "Applying database migrations..."
    & .venv\Scripts\alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "alembic upgrade failed." }
    if ($Seed) {
        & .venv\Scripts\python -m app.seed
        if ($LASTEXITCODE -ne 0) { throw "Seeding failed." }
    }
}
finally { Pop-Location }

Push-Location (Join-Path $root "frontend")
try {
    Write-Host "Installing frontend dependencies..."
    npm install --no-fund --no-audit
    if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
}
finally { Pop-Location }

Write-Host ""
Write-Host "Setup complete. Start the app in two terminals:" -ForegroundColor Green
Write-Host "  backend : cd backend;  .venv\Scripts\uvicorn app.main:app --reload --port 8000"
Write-Host "  frontend: cd frontend; npm run dev        -> http://localhost:5173"
