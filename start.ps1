# Foncier-Express - Script de Démarrage (Windows)
# Usage: .\start.ps1
#
# Lance le backend FastAPI et le frontend Vue dans deux fenêtres séparées.
# Aucune base de données à démarrer : l'application est libre et sans compte,
# l'API lit un simple fichier DuckDB en lecture seule.

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   FONCIER-EXPRESS - Demarrage              " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# --- Verifications prealables -------------------------------------------------

$pythonExe = ".\.venv\Scripts\python.exe"
if (-Not (Test-Path $pythonExe)) { $pythonExe = ".\venv\Scripts\python.exe" }
if (-Not (Test-Path $pythonExe)) {
    Write-Host "`nERREUR: environnement Python introuvable." -ForegroundColor Red
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "  pip install -e `".[dev]`"" -ForegroundColor Yellow
    exit 1
}

if (-Not (Test-Path ".\frontend\node_modules")) {
    Write-Host "`nERREUR: dependances frontend absentes." -ForegroundColor Red
    Write-Host "  cd frontend ; npm install" -ForegroundColor Yellow
    exit 1
}

# Base DuckDB : chemin lu dans .env, defaut data/dept35.duckdb
$duckdbPath = "data\dept35.duckdb"
if (Test-Path ".env") {
    $line = Select-String -Path ".env" -Pattern "^DUCKDB_PATH=" -ErrorAction SilentlyContinue
    if ($line) { $duckdbPath = ($line.Line -replace "^DUCKDB_PATH=", "").Trim() }
}
if (-Not (Test-Path $duckdbPath)) {
    Write-Host "`nATTENTION: base analytique introuvable : $duckdbPath" -ForegroundColor Yellow
    Write-Host "  L'API demarrera, mais sans donnees." -ForegroundColor Yellow
    Write-Host "  Construire la base : python data-pipeline\etl_build_dept.py 35" -ForegroundColor Yellow
}

# Le frontend a besoin de savoir ou joindre l'API
if (-Not (Test-Path ".\frontend\.env")) {
    Copy-Item ".\frontend\.env.example" ".\frontend\.env"
    Write-Host "`n  frontend\.env cree depuis .env.example" -ForegroundColor DarkGray
}

# --- Backend ------------------------------------------------------------------

Write-Host "`n[1/2] Backend FastAPI..." -ForegroundColor Yellow
$backend = Start-Process powershell -PassThru -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$PWD'; & '$pythonExe' -m uvicorn app.main:app --reload --port 8000"
)
Write-Host "      http://localhost:8000  (PID $($backend.Id))" -ForegroundColor Green

# --- Frontend -----------------------------------------------------------------

Write-Host "`n[2/2] Frontend Vue..." -ForegroundColor Yellow
$frontend = Start-Process powershell -PassThru -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$PWD\frontend'; npm run dev"
)
Write-Host "      http://localhost:5173  (PID $($frontend.Id))" -ForegroundColor Green

# --- Resume -------------------------------------------------------------------

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   APPLICATION PRETE                        " -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Application : http://localhost:5173" -ForegroundColor White
Write-Host "   API (docs)  : http://localhost:8000/docs" -ForegroundColor White
Write-Host "   Sante       : http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "   Pour arreter : fermer les deux fenetres PowerShell" -ForegroundColor DarkGray
Write-Host ""

$openBrowser = Read-Host "Ouvrir le navigateur ? (O/n)"
if ($openBrowser -ne "n") {
    Start-Process "http://localhost:5173"
}
