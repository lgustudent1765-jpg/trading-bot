# file: scripts/start.ps1
# Run this script to start the algo-trade system.
# Double-click or run from PowerShell.

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

# Load .env file if it exists.
$EnvFile = Join-Path $ProjectDir ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]*)\s*=\s*(.*)\s*$") {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim().Trim('"').Trim("'")
            if ($key -and -not [System.Environment]::GetEnvironmentVariable($key)) {
                [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
            }
        }
    }
    Write-Host "[OK] Loaded .env"
} else {
    Write-Host "[WARN] No .env file found — copy .env.template to .env and fill in values"
}

# Ensure logs and data directories exist.
New-Item -ItemType Directory -Force -Path "$ProjectDir\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$ProjectDir\data" | Out-Null

# Determine mode from .env or default to paper.
$Mode = if ($env:MODE) { $env:MODE } else { "paper" }
Write-Host "[OK] Starting in $Mode mode..."
Write-Host "[OK] Dashboard: http://localhost:$($env:API_PORT ?? '8080')"
Write-Host "     Press Ctrl+C to stop."
Write-Host ""

python -m src.cli.main --mode $Mode --config config.yaml
