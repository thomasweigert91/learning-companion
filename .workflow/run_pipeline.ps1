Write-Host "=== 1. Validierung: Ticket ===" -ForegroundColor Yellow
.\.workflow\hooks\validate_ticket.ps1
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`n=== 2. Validierung: Implementierungs-Plan ===" -ForegroundColor Yellow
.\.workflow\hooks\validate_plan.ps1
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`n=== 3. Validierung: Code & Tests ===" -ForegroundColor Yellow
.\.workflow\hooks\validate_code.ps1
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`n=== 4. Validierung: Review ===" -ForegroundColor Yellow
.\.workflow\hooks\validate_review.ps1
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`nPipeline komplett durchgelaufen: Anwendung einsatzbereit!" -ForegroundColor Green
