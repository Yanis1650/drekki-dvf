# Foncier-Express - Script de Démarrage
# Usage: .\start.ps1

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   FONCIER-EXPRESS - Demarrage Complet     " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# 1. Demarrer Docker PostGIS
Write-Host "`n[1/3] Demarrage de PostgreSQL/PostGIS..." -ForegroundColor Yellow
docker start foncier-postgis 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "      PostGIS demarre sur le port 5433" -ForegroundColor Green
} else {
    Write-Host "      PostGIS deja actif ou erreur" -ForegroundColor DarkYellow
}

# Attendre que PostgreSQL soit pret
Write-Host "      Attente de PostgreSQL (3s)..."
Start-Sleep -Seconds 3

# 2. Demarrer le Backend FastAPI
Write-Host "`n[2/3] Demarrage du Backend FastAPI..." -ForegroundColor Yellow
$pythonExe = ".\.venv\Scripts\python.exe"
if (-Not (Test-Path $pythonExe)) { $pythonExe = ".\venv\Scripts\python.exe" }
if (-Not (Test-Path $pythonExe)) {
    Write-Host "ERREUR: Environnement Python introuvable." -ForegroundColor Red
    Write-Host "Creer un seul environnement: python -m venv .venv" -ForegroundColor Yellow
    Write-Host "Puis: .\.venv\Scripts\Activate.ps1 ; pip install -e `".[dev]`"" -ForegroundColor Yellow
    exit 1
}
$backendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; & '$pythonExe' -m uvicorn app.main:app --reload --port 8000" -PassThru
Write-Host "      Backend demarre sur http://localhost:8000" -ForegroundColor Green
Write-Host "      PID: $($backendJob.Id)" -ForegroundColor DarkGray

# 3. Demarrer le Frontend Vue.js
Write-Host "`n[3/3] Demarrage du Frontend Vue.js..." -ForegroundColor Yellow
$frontendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\frontend'; npm run dev" -PassThru
Write-Host "      Frontend demarre sur http://localhost:5173" -ForegroundColor Green
Write-Host "      PID: $($frontendJob.Id)" -ForegroundColor DarkGray

# Resume
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   APPLICATION PRETE !                      " -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Frontend:  http://localhost:5173" -ForegroundColor White
Write-Host "   API Docs:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "   PostGIS:   localhost:5433" -ForegroundColor White
Write-Host ""
Write-Host "   Pour arreter: Fermez les fenetres PowerShell" -ForegroundColor DarkGray
Write-Host "   ou utilisez: docker stop foncier-postgis" -ForegroundColor DarkGray
Write-Host ""

# Ouvrir le navigateur
$openBrowser = Read-Host "Ouvrir le navigateur ? (O/n)"
if ($openBrowser -ne "n") {
    Start-Process "http://localhost:5173"
}
