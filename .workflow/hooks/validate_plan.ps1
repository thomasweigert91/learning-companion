$file = Join-Path $PSScriptRoot "..\artifacts\plan.md"

if (-not (Test-Path $file)) {
    Write-Host "Hook-Fehler: Datei '$file' wurde nicht gefunden!" -ForegroundColor Red
    exit 1
}

$content = Get-Content -Path $file -Raw

if ($content -notmatch "## 1\. Betroffene Dateien") {
    Write-Host "Hook-Fehler: Abschnitt '## 1. Betroffene Dateien' fehlt im Plan!" -ForegroundColor Red
    exit 1
}

if ($content -notmatch "## 2\. Datenmodelle") {
    Write-Host "Hook-Fehler: Abschnitt '## 2. Datenmodelle & Migrationen' fehlt im Plan!" -ForegroundColor Red
    exit 1
}

if ($content -notmatch "## 3\. Schrittweise Umsetzung") {
    Write-Host "Hook-Fehler: Abschnitt '## 3. Schrittweise Umsetzung' fehlt im Plan!" -ForegroundColor Red
    exit 1
}

if ($content -notmatch "- \[ \]") {
    Write-Host "Hook-Fehler: Mindestens ein offener Task '- [ ]' unter 'Schrittweise Umsetzung' erforderlich!" -ForegroundColor Red
    exit 1
}

Write-Host "Implementierungs-Plan erfolgreich validiert." -ForegroundColor Green
exit 0
