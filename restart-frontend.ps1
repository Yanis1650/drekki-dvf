# Foncier-Express - Script de Redémarrage Frontend
# Usage: .\restart-frontend.ps1

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   REDEMARRAGE FRONTEND UNIQUEMENT         " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Trouver et arrêter les processus Node.js (Vite)
Write-Host "`n[1/2] Arret du frontend existant..." -ForegroundColor Yellow
$viteProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -like "*vite*" -or $_.CommandLine -like "*vite*"
}

if ($viteProcesses) {
    $viteProcesses | ForEach-Object {
        Write-Host "      Arret du processus PID: $($_.Id)" -ForegroundColor DarkGray
        Stop-Process -Id $_.Id -Force
    }
    Write-Host "      Frontend arrete" -ForegroundColor Green
} else {
    Write-Host "      Aucun processus frontend actif" -ForegroundColor DarkYellow
}

Start-Sleep -Seconds 2

# Redémarrer le Frontend
Write-Host "`n[2/2] Redemarrage du Frontend Vue.js..." -ForegroundColor Yellow
$frontendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\frontend'; npm run dev" -PassThru
Write-Host "      Frontend demarre sur http://localhost:5173" -ForegroundColor Green
Write-Host "      PID: $($frontendJob.Id)" -ForegroundColor DarkGray

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "   FRONTEND REDÉMARRE !                     " -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Frontend:  http://localhost:5173" -ForegroundColor White
Write-Host "   Les modifications de App.vue sont maintenant actives" -ForegroundColor Green
Write-Host ""
