$file = Join-Path $PSScriptRoot "..\artifacts\ticket.md"

if (-not (Test-Path $file)) {
    Write-Host "Hook-Fehler: Datei '$file' wurde nicht gefunden!" -ForegroundColor Red
    exit 1
}

$content = Get-Content -Path $file -Raw

if ($content -notmatch "## 1\. Problem / Ziel") {
    Write-Host "Hook-Fehler: Abschnitt '## 1. Problem / Ziel' fehlt im Ticket!" -ForegroundColor Red
    exit 1
}

if ($content -notmatch "## 2\. Akzeptanzkriterien") {
    Write-Host "Hook-Fehler: Abschnitt '## 2. Akzeptanzkriterien' fehlt im Ticket!" -ForegroundColor Red
    exit 1
}

if ($content -notmatch "- \[ \]") {
    Write-Host "Hook-Fehler: Mindestens eine offene Checkbox '- [ ]' unter Akzeptanzkriterien erforderlich!" -ForegroundColor Red
    exit 1
}

Write-Host "Ticket erfolgreich validiert." -ForegroundColor Green
exit 0
