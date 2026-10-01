$logFile = Join-Path $PSScriptRoot "..\artifacts\hooks_logging.log"
"" | Set-Content -Path $logFile -Encoding utf8

Write-Host "Starte Code-Validierung (Django Check & Tests)..." -ForegroundColor Cyan

# 1. Django System-Check
$checkOutput = python manage.py check 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Django System Check fehlgeschlagen!" -ForegroundColor Red
    $checkOutput | Out-File -FilePath $logFile -Encoding utf8
    exit 1
}

# 2. Django Tests ausführen
$testOutput = python manage.py test 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Django Tests fehlgeschlagen!" -ForegroundColor Red
    $testOutput | Out-File -FilePath $logFile -Encoding utf8
    exit 1
}

Write-Host "Code-Validierung erfolgreich bestanden." -ForegroundColor Green
exit 0
