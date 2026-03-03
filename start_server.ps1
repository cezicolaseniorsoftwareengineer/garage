# GARAGE – Iniciar servidor FastAPI na porta 8081
# Uso: .\start_server.ps1

$VENV_PYTHON = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$GARAGE_DIR  = Join-Path $PSScriptRoot "Garage"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Error "Python nao encontrado em: $VENV_PYTHON"
    Write-Host "Execute: python -m venv .venv  e depois pip install -r Garage/requirements.txt"
    exit 1
}

Write-Host "========================================================"
Write-Host " GARAGE Game Server"
Write-Host " URL: http://127.0.0.1:8000"
Write-Host " Landing: http://127.0.0.1:8000/"
Write-Host " Jogo:    http://127.0.0.1:8000/jogo"
Write-Host " Docs:    http://127.0.0.1:8000/docs"
Write-Host "========================================================";

Set-Location $GARAGE_DIR
& $VENV_PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
