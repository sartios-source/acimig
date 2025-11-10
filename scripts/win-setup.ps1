# Windows Setup Script for ACI Analysis Tool
Write-Host "ACI Analysis Tool - Windows Setup" -ForegroundColor Green

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    exit 1
}

$pythonVersion = & python --version
Write-Host "Found: $pythonVersion" -ForegroundColor Green

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    & python -m venv venv
}

# Activate and install
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
& pip install -r requirements.txt

Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "Starting application..." -ForegroundColor Cyan
& python app.py
