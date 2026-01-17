# Script PowerShell pour exécuter l'ETL Densification
# Utilise l'environnement virtuel Python du projet

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "ETL Densification - Execution avec environnement virtuel" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Vérifier que l'environnement virtuel existe
if (-Not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "ERREUR: Environnement virtuel introuvable!" -ForegroundColor Red
    Write-Host "Chemin attendu: venv\Scripts\python.exe" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Créer l'environnement virtuel avec:" -ForegroundColor Yellow
    Write-Host "  python -m venv venv" -ForegroundColor White
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host "  pip install -r requirements.txt" -ForegroundColor White
    exit 1
}

Write-Host "✓ Environnement virtuel trouvé" -ForegroundColor Green
Write-Host ""

# Vérifier que le fichier ETL existe
if (-Not (Test-Path "data-pipeline\etl_densification.py")) {
    Write-Host "ERREUR: Script ETL introuvable!" -ForegroundColor Red
    Write-Host "Chemin attendu: data-pipeline\etl_densification.py" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Script ETL trouvé" -ForegroundColor Green
Write-Host ""

# Exécuter l'ETL avec l'environnement virtuel
Write-Host "Lancement de l'ETL..." -ForegroundColor Cyan
Write-Host ""

& .\venv\Scripts\python.exe data-pipeline\etl_densification.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "✅ ETL Densification terminé avec succès!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Prochaines étapes:" -ForegroundColor Cyan
    Write-Host "  1. Tester l'API: curl http://localhost:8000/api/v1/land/parcelles/35238000BV0001/densification" -ForegroundColor White
    Write-Host "  2. Vérifier le frontend: cliquer sur une parcelle à Rennes" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "❌ ETL Densification a échoué (code: $LASTEXITCODE)" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Vérifier les erreurs ci-dessus" -ForegroundColor Yellow
    exit $LASTEXITCODE
}
