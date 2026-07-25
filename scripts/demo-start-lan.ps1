# =====================================================================
#  Sentinel — Option B launcher (LAN, no tunnel)
# =====================================================================
#  For the app's DEVELOPMENT BUILD (Option B / app-owned OAuth). No public
#  tunnel is needed: OAuth happens on the phone against fixed identities, and
#  the backend only needs to be reachable by the phone over the local network.
#
#  Starts Ollama + backend (0.0.0.0) + Discord bot, points mobile\.env at your
#  PC's LAN IP, and reminds you to start Metro with --dev-client.
#
#  Usage:  powershell -ExecutionPolicy Bypass -File .\scripts\demo-start-lan.ps1
#  Stop:   powershell -ExecutionPolicy Bypass -File .\scripts\demo-stop.ps1
# =====================================================================

$ErrorActionPreference = 'Stop'
$root    = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$mobile  = Join-Path $root 'mobile'
$py      = Join-Path $backend '.venv\Scripts\python.exe'
$ollama  = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
$logDir  = Join-Path $env:TEMP 'sentinel-demo'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Say($msg, $color = 'Cyan') { Write-Host "==> $msg" -ForegroundColor $color }

if (-not (Test-Path $py)) { throw "Backend venv not found at $py." }

# --- Detect LAN IPv4 --------------------------------------------------
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' } |
  Sort-Object -Property @{ Expression = { $_.InterfaceAlias -like '*Wi-Fi*' } } -Descending |
  Select-Object -First 1).IPAddress
if (-not $ip) { throw "Could not determine a LAN IP address." }
$apiUrl = "http://$ip`:8000"
Say "LAN IP: $ip  ->  API base $apiUrl" 'Green'

# --- Ollama -----------------------------------------------------------
Say 'Ensuring Ollama is running...'
try { Invoke-RestMethod 'http://localhost:11434/api/tags' -TimeoutSec 3 | Out-Null }
catch {
  if (Test-Path $ollama) { Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden; Start-Sleep 5 }
  else { Write-Host 'Ollama not found; classifier will fail until running.' -ForegroundColor Yellow }
}

# --- Point mobile app at the LAN IP ----------------------------------
Say 'Updating mobile\.env EXPO_PUBLIC_API_URL...'
$mbEnv = Join-Path $mobile '.env'
if (Test-Path $mbEnv) {
  $c = Get-Content $mbEnv -Raw
  if ($c -match '(?m)^EXPO_PUBLIC_API_URL=.*$') {
    $c = $c -replace '(?m)^EXPO_PUBLIC_API_URL=.*$', "EXPO_PUBLIC_API_URL=$apiUrl"
  } else {
    $c = "EXPO_PUBLIC_API_URL=$apiUrl`n" + $c
  }
  Set-Content $mbEnv $c -NoNewline
} else {
  Set-Content $mbEnv "EXPO_PUBLIC_API_URL=$apiUrl`n" -NoNewline
}

# Backend workers (Discord bot / Gmail poller) POST to /triage using
# SENTINEL_APP_BASE_URL — keep it pointed at the same LAN address.
Say 'Updating backend\.env SENTINEL_APP_BASE_URL...'
$beEnv = Join-Path $backend '.env'
if (Test-Path $beEnv) {
  $bc = Get-Content $beEnv -Raw
  if ($bc -match '(?m)^SENTINEL_APP_BASE_URL=.*$') {
    $bc = $bc -replace '(?m)^SENTINEL_APP_BASE_URL=.*$', "SENTINEL_APP_BASE_URL=$apiUrl"
  } else {
    $bc = $bc.TrimEnd() + "`nSENTINEL_APP_BASE_URL=$apiUrl`n"
  }
  Set-Content $beEnv $bc -NoNewline
}

# --- Backend (0.0.0.0 so the phone can reach it) ---------------------
Say 'Starting backend on 0.0.0.0:8000...'
$backendProc = Start-Process -FilePath $py `
  -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' `
  -WorkingDirectory $backend -PassThru -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'backend.log') `
  -RedirectStandardError  (Join-Path $logDir 'backend.err.log')
Start-Sleep 5
try { (Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 5) | Out-Null; Say 'Backend is up.' 'Green' }
catch { Write-Host "Backend did not answer yet; see $logDir" -ForegroundColor Yellow }

# --- Discord bot ------------------------------------------------------
Say 'Starting Discord gateway bot...'
$botProc = Start-Process -FilePath $py `
  -ArgumentList '-m','app.workers.discord_bot' `
  -WorkingDirectory $backend -PassThru -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'bot.log') `
  -RedirectStandardError  (Join-Path $logDir 'bot.err.log')

# --- Gmail poller -----------------------------------------------------
Say 'Starting Gmail poller...'
$gmailProc = Start-Process -FilePath $py `
  -ArgumentList '-m','app.workers.gmail_poller' `
  -WorkingDirectory $backend -PassThru -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'gmail.log') `
  -RedirectStandardError  (Join-Path $logDir 'gmail.err.log')

# --- Metro (dev-client) — DETACHED so it never grabs your terminal ----
# We run Metro hidden with stdout/stderr redirected to log files. Because the
# child has no TTY, the Expo CLI won't enable its interactive mouse-reporting UI
# (which was the source of the [<..M escape-code flood) — so we do NOT set CI=1.
# CI mode would DISABLE file watching / hot reload, freezing the bundle at
# startup, which is exactly what we want to avoid during iteration.
Say 'Starting Metro (dev-client, watch mode, background)...'
$npx = (Get-Command npx.cmd -ErrorAction SilentlyContinue).Source
if (-not $npx) { $npx = (Get-Command npx -ErrorAction SilentlyContinue).Source }
Remove-Item Env:CI -ErrorAction SilentlyContinue  # ensure watch mode is enabled
$metroProc = Start-Process -FilePath $npx `
  -ArgumentList 'expo','start','--dev-client','--port','8081' `
  -WorkingDirectory $mobile -PassThru -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'metro.log') `
  -RedirectStandardError  (Join-Path $logDir 'metro.err.log')

# --- Record PIDs for demo-stop ---------------------------------------
@{ backend = $backendProc.Id; bot = $botProc.Id; gmail = $gmailProc.Id; metro = $metroProc.Id; tunnel = $null; url = $apiUrl } |
  ConvertTo-Json | Set-Content (Join-Path $logDir 'pids.json')

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host " SENTINEL (Option B / LAN) IS UP - no tunnel, nothing interactive" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host " Backend (phone reaches this) : $apiUrl"
Write-Host " Metro (dev build connects)   : http://$ip`:8081"
Write-Host ""
Write-Host " On your phone: open the 'Sentinel' dev-build app (same Wi-Fi)."
Write-Host " If it shows a dev screen, enter: http://$ip`:8081"
Write-Host ""
Write-Host " Redirect URIs are FIXED (register once):"
Write-Host "   Discord: sentinel://oauthredirect"
Write-Host "   Google : Android OAuth client (package com.sentinel.app + EAS SHA-1)"
Write-Host ""
Write-Host " Logs: $logDir     Stop: .\scripts\demo-stop.ps1"
Write-Host "======================================================================" -ForegroundColor Green
