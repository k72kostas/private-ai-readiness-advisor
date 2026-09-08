Set-Location $PSScriptRoot

Set-ExecutionPolicy `
    -Scope Process `
    -ExecutionPolicy Bypass

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

chcp 65001 | Out-Null

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Error "Virtual environment not found at .venv"
    exit 1
}

Write-Host ""
Write-Host "Starting PARA-GIP..."
Write-Host ""

& ".\.venv\Scripts\python.exe" --version

# Streamlit may write informational messages to stderr.
# Do not treat those messages as terminating PowerShell errors.
$ErrorActionPreference = "Continue"

& ".\.venv\Scripts\python.exe" `
    -m streamlit `
    run app/main.py `
    --server.address 127.0.0.1 `
    --server.port 8501