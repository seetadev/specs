# Setup script for libp2p specs local development (Windows / PowerShell)
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $ProjectRoot

Write-Host "Setting up libp2p specs development environment..." -ForegroundColor Green

function Find-CompatiblePython {
    $output = & python (Join-Path $ScriptDir "dev_setup.py") 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $output) { return $null }
    return $output.Trim()
}

function Activate-Venv {
    $activate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
    if (-not (Test-Path $activate)) { throw "Virtual environment is missing $activate" }
    . $activate
}

function Ensure-Venv {
    if ($env:VIRTUAL_ENV) { return }
    $pythonBin = Find-CompatiblePython
    if (-not $pythonBin) {
        Write-Host "Python 3.10+ is required for Grip and local tooling." -ForegroundColor Red
        exit 1
    }
    Write-Host "Creating virtual environment with $pythonBin..." -ForegroundColor Yellow
    & $pythonBin -m venv .venv
    Activate-Venv
}

function Test-VenvPython {
    & python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Active Python is older than 3.10. Remove .venv and re-run setup." -ForegroundColor Red
        exit 1
    }
}

Ensure-Venv
Test-VenvPython

Write-Host "Installing Python tools (grip)..." -ForegroundColor Green
python -m pip install --upgrade pip
python -m pip install grip

if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "Installing Node dev dependencies..." -ForegroundColor Green
    npm install
} else {
    Write-Host "npm not found; install Node.js to run npm run lint." -ForegroundColor Yellow
}

Write-Host "Setup complete! Run: npm run dev" -ForegroundColor Green
