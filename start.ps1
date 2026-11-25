# Starts the campus server (MEC, :8000) and the portal (:8001), then opens the portal.
#   .\start.ps1                 use this laptop's Wi-Fi IP
#   .\start.ps1 -Ip 100.64.0.5  use another address (e.g. Tailscale)
param([string]$Ip)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Run .\setup.ps1 first." }
if (-not $Ip) {
    $Ip = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } |
        Select-Object -First 1).IPv4Address.IPAddress
}
if (-not $Ip) { throw "No network address found. Run: .\start.ps1 -Ip <address>" }
foreach ($m in "w600k_mbf.onnx", "face_detection_yunet_2023mar.onnx") {
    if (-not (Test-Path "$root\models\$m")) { & $py "$root\enrollment\fetch_models.py"; break }
}
Set-Location "$root\server"

# The certificate names this address: a new address means a new certificate and server code.
$stamp = "data\tls\ip.txt"
if (-not (Test-Path "data\tls\cert.pem") -or -not (Test-Path $stamp) -or (Get-Content $stamp) -ne $Ip) {
    & $py scripts\gen_dev_cert.py $Ip
    Set-Content $stamp $Ip
    Write-Warning "New certificate for $Ip. Enter the new server code (below) in the app."
}

$env:ATTEND_MEC_URL = "https://localhost:8000"
$env:ATTEND_MEC_CA = "$root\server\data\tls\cert.pem"
$tls = "--host 0.0.0.0 --ssl-keyfile data/tls/key.pem --ssl-certfile data/tls/cert.pem"
# The MEC needs the portal's public key, which the portal creates on first start: create it up front.
& $py -c "from common.keys import portal_signing_key; from common.settings import Settings; portal_signing_key(Settings.from_env())"
$code = & $py -c "from cryptography import x509; from cryptography.hazmat.primitives import hashes; h = x509.load_pem_x509_certificate(open('data/tls/cert.pem','rb').read()).fingerprint(hashes.SHA256()).hex()[:16]; print('-'.join(h[i:i+4] for i in range(0,16,4)))"
$mec = Start-Process $py "-m uvicorn mec_server.app:create_app --factory --port 8000 $tls" -PassThru -NoNewWindow
$portal = Start-Process $py "-m uvicorn portal.app:create_app --factory --port 8001 $tls" -PassThru -NoNewWindow
try {
    Start-Sleep -Seconds 4
    if ($mec.HasExited -or $portal.HasExited) { throw "A server failed to start (is port 8000 or 8001 in use?)" }
    Write-Host "`nPortal:         https://localhost:8001"
    Write-Host "In the phone:   portal https://${Ip}:8001   campus server https://${Ip}:8000"
    Write-Host "Server code:    $code"
    Write-Host "Press Ctrl+C to stop.`n"
    Start-Process "https://localhost:8001"
    Wait-Process -Id $mec.Id, $portal.Id
} finally {
    Set-Location $root
    $mec, $portal | Where-Object { -not $_.HasExited } | Stop-Process -Force
}
