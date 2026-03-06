# file: scripts/install_service.ps1
# Installs algo-trade as a Windows background service using NSSM.
# Run as Administrator.
#
# Prerequisites:
#   winget install NSSM.NSSM
#
# Usage:
#   Right-click -> "Run with PowerShell" (as Administrator)

$ServiceName = "AlgoTrade"
$ProjectDir  = Split-Path -Parent $PSScriptRoot
$Python      = (Get-Command python).Source
$NssmPath    = (Get-Command nssm -ErrorAction SilentlyContinue)?.Source

if (-not $NssmPath) {
    Write-Error "NSSM not found. Install with: winget install NSSM.NSSM"
    exit 1
}

Write-Host "Installing $ServiceName service..."

nssm install $ServiceName $Python "-m src.cli.main --mode paper --config config.yaml"
nssm set $ServiceName AppDirectory $ProjectDir
nssm set $ServiceName AppEnvironmentExtra "DOTENV_PATH=$ProjectDir\.env"
nssm set $ServiceName AppStdout "$ProjectDir\logs\service-stdout.log"
nssm set $ServiceName AppStderr "$ProjectDir\logs\service-stderr.log"
nssm set $ServiceName AppRotateFiles 1
nssm set $ServiceName AppRotateBytes 10485760
nssm set $ServiceName Start SERVICE_AUTO_START
nssm set $ServiceName ObjectName LocalSystem

Write-Host ""
Write-Host "[OK] Service installed."
Write-Host "     Start:   nssm start $ServiceName"
Write-Host "     Stop:    nssm stop $ServiceName"
Write-Host "     Status:  nssm status $ServiceName"
Write-Host "     Remove:  nssm remove $ServiceName confirm"
Write-Host ""
Write-Host "Starting service now..."
nssm start $ServiceName
