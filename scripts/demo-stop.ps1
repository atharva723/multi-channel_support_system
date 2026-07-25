# =====================================================================
#  Sentinel — stop all demo processes started by demo-start.ps1
# =====================================================================
$logDir = Join-Path $env:TEMP 'sentinel-demo'
$pidFile = Join-Path $logDir 'pids.json'

if (-not (Test-Path $pidFile)) {
  Write-Host "No pids.json found ($pidFile). Nothing recorded to stop." -ForegroundColor Yellow
  return
}

$pids = Get-Content $pidFile -Raw | ConvertFrom-Json
foreach ($name in 'backend', 'bot', 'gmail', 'metro', 'tunnel') {
  $processId = $pids.$name
  if ($processId) {
    try {
      Stop-Process -Id $processId -Force -ErrorAction Stop
      Write-Host "Stopped $name (PID $processId)." -ForegroundColor Green
    } catch {
      Write-Host "Could not stop $name (PID $processId) - may already be gone." -ForegroundColor Yellow
    }
  }
}
Remove-Item $pidFile -ErrorAction SilentlyContinue
Write-Host "Done. (If you ran 'npx expo start' separately, close that terminal too.)"
