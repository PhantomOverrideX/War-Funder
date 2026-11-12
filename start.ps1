# If you see "not digitally signed", run instead:
#   powershell -ExecutionPolicy Bypass -File .\start.ps1
# Or double-click start.bat (recommended on locked-down PCs).
#
# BIOBENCH local launcher
# Starts python -m http.server and opens the game in your default browser.

$ErrorActionPreference = "Stop"
$Port = 8000
$Root = $PSScriptRoot
if (-not $Root) { $Root = Get-Location }

Set-Location $Root

# Prefer py launcher, then python3, then python
$python = $null
foreach ($cmd in @("py", "python3", "python")) {
    try {
        $null = Get-Command $cmd -ErrorAction Stop
        $python = $cmd
        break
    } catch {}
}

if (-not $python) {
    Write-Host "Python was not found. Install Python 3 and ensure it is on PATH." -ForegroundColor Red
    exit 1
}

$url = "http://localhost:$Port/"
Write-Host "Serving $Root on $url" -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Gray
Write-Host ""

# Open browser after a short delay so the server can bind
Start-Job -ScriptBlock {
    param($u)
    Start-Sleep -Seconds 1
    Start-Process $u
} -ArgumentList $url | Out-Null

# Also try immediate open (works if server starts fast enough)
try { Start-Process $url } catch {}

if ($python -eq "py") {
    & py -3 -m http.server $Port
} else {
    & $python -m http.server $Port
}
