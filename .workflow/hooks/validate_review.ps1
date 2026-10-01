$file = Join-Path $PSScriptRoot "..\artifacts\review.md"

if (-not (Test-Path $file)) {
    Write-Host "Hook-Fehler: Review-Datei '$file' fehlt!" -ForegroundColor Red
    exit 1
}

$content = Get-Content -Path $file -Raw

if ($content -notmatch "APPROVED") {
    Write-Host "Hook-Fehler: Code Review wurde noch nicht freigegeben (Status ist nicht APPROVED)!" -ForegroundColor Red
    exit 1
}

Write-Host "Review erfolgreich: Anwendung freigegeben!" -ForegroundColor Green
exit 0
