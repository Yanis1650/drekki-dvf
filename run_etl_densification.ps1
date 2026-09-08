# Script PowerShell pour exécuter l'ETL Densification
# Utilise l'environnement virtuel Python du projet

param(
    [string]$Dept = "35",
    [string]$Db = ""
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "ETL Densification - Execution avec environnement virtuel" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Vérifier que l'environnement virtuel existe (.venv = environnement unique du projet)
$racine = $PSScriptRoot
$pythonExe = Join-Path $racine ".venv\Scripts\python.exe"
if (-Not (Test-Path $pythonExe)) {
    Write-Host "ERREUR: Environnement Python introuvable!" -ForegroundColor Red
    Write-Host "Chemin attendu: .venv\Scripts\python.exe" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Creer l'environnement unique avec:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor White
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host "  pip install -e `".[dev]`"" -ForegroundColor White
    exit 1
}

Write-Host "OK Environnement .venv trouve" -ForegroundColor Green
Write-Host ""

# L'etape vit dans le paquet etl_build_steps, celui que le pipeline execute et
# que tests/test_densification_step.py couvre. Elle s'appelle en module, depuis
# data-pipeline : le paquet doit etre sur le chemin d'import.
$pipeline = Join-Path $racine "data-pipeline"
$etape = Join-Path $pipeline "etl_build_steps\densification_cli.py"
if (-Not (Test-Path $etape)) {
    Write-Host "ERREUR: Etape ETL introuvable!" -ForegroundColor Red
    Write-Host "Chemin attendu: data-pipeline\etl_build_steps\densification_cli.py" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Etape ETL trouvée" -ForegroundColor Green
Write-Host ""

# Exécuter l'ETL avec l'environnement virtuel
Write-Host "Lancement de l'ETL sur le departement $Dept..." -ForegroundColor Cyan
Write-Host ""

$arguments = @("-m", "etl_build_steps.densification_cli", $Dept)
if ($Db -ne "") {
    $arguments += @("--db", $Db)
}

Push-Location $pipeline
try {
    & $pythonExe $arguments
} finally {
    Pop-Location
}

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
