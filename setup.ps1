# One-time setup of the server on a Windows PC. Safe to run again.
#   .\setup.ps1          asks for your teacher account
#   .\setup.ps1 -Demo    creates teacher demo / demo-password with five students
param([switch]$Demo)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = "$root\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Install Python 3.10+ from python.org, then run this again." }
    python -c "import sys; sys.exit(sys.version_info < (3, 10))"
    if ($LASTEXITCODE -ne 0) { throw "Python 3.10 or newer is required." }
    python -m venv "$root\.venv"
}
Write-Host "Installing Python packages..."
& $py -m pip install -q -r "$root\server\requirements.txt" -r "$root\enrollment\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "Package installation failed." }
& $py "$root\enrollment\fetch_models.py"
if ($LASTEXITCODE -ne 0) { throw "Model download failed." }

Push-Location "$root\server"
try {
    $failed = $false
    if ($Demo) { & $py -m portal.cli demo; $failed = $LASTEXITCODE -ne 0 }
    else {
        $user = Read-Host "Teacher username (Enter to skip)"
        if ($user) { & $py -m portal.cli add-teacher $user (Read-Host "Your name"); $failed = $LASTEXITCODE -ne 0 }
    }
    if ($failed) { Write-Warning "Teacher account was not created. Run .\setup.ps1 again." }
} finally { Pop-Location }

$rule = "New-NetFirewallRule -DisplayName Attendance -Direction Inbound -Protocol TCP -LocalPort 8000,8001 -Action Allow"
if (-not (Get-NetFirewallRule -DisplayName Attendance -ErrorAction SilentlyContinue)) {
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole("Administrator")
    if ($admin) { Invoke-Expression $rule | Out-Null; Write-Host "Firewall opened for ports 8000 and 8001." }
    else { Write-Warning "So the phone can connect, run once in an administrator PowerShell:`n  $rule" }
}
Write-Host "`nSetup done. Start the server with: .\start.ps1"
