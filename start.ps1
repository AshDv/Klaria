$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$serverPath = Join-Path $projectRoot "server"
$webPath = Join-Path $projectRoot "web"
$pythonPath = Join-Path $serverPath ".venv\Scripts\python.exe"

Write-Host "Préparation du backend Scribe..." -ForegroundColor Cyan
if (-not (Test-Path $pythonPath)) {
  python -m venv (Join-Path $serverPath ".venv")
}
& $pythonPath -m pip install -r (Join-Path $serverPath "requirements.txt")
if (-not (Test-Path (Join-Path $serverPath ".env"))) {
  Copy-Item (Join-Path $serverPath ".env.example") (Join-Path $serverPath ".env")
  Write-Host "Configurez MISTRAL_API_KEY et, si nécessaire, Google SSO dans server\.env." -ForegroundColor Yellow
}

Write-Host "Préparation du frontend..." -ForegroundColor Cyan
Push-Location $webPath
npm install
Pop-Location

Write-Host "Lancement de Scribe..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$serverPath'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$webPath'; npm run dev"

Start-Sleep -Seconds 5
Start-Process "http://localhost:5174"
Write-Host "Scribe : http://localhost:5174" -ForegroundColor Green
