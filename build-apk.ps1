# Builds the app with the current server certificate and face model baked in.
# Installs it too if a phone is connected with USB debugging on.
#   .\build-apk.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$ip = Get-Content "$root\server\data\tls\ip.txt" -ErrorAction SilentlyContinue
if (-not (Test-Path "$root\models\w600k_mbf.onnx")) { throw "Face model missing. Run .\setup.ps1 first." }

# Gradle 8.11 needs JDK 17 to 21.
function Test-Jdk($path) { $path -and (Test-Path "$path\release") -and ((Get-Content "$path\release") -match '^JAVA_VERSION="(17|18|19|20|21)\b') }
$dirs = "$HOME\.jdks", "$env:ProgramFiles\Java", "$env:ProgramFiles\Eclipse Adoptium", "$env:ProgramFiles\Microsoft"
$jdk = @($env:JAVA_HOME) + @(Get-ChildItem $dirs -Directory -ErrorAction SilentlyContinue | ForEach-Object FullName) +
    @("$env:ProgramFiles\Android\Android Studio\jbr") | Where-Object { Test-Jdk $_ } | Select-Object -First 1
if (-not $jdk) { throw "No JDK 17-21 found. Install one (winget install Microsoft.OpenJDK.21) or set JAVA_HOME." }
$env:JAVA_HOME = $jdk

Set-Location "$root\android"
if (-not (Test-Path local.properties)) {
    $found = @($env:ANDROID_HOME, "$env:LOCALAPPDATA\Android\Sdk") | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if (-not $found) { throw "Android SDK not found. Install Android Studio, or set ANDROID_HOME." }
    Set-Content local.properties "sdk.dir=$($found.Replace('\', '/'))" -Encoding ascii
}
$gradleArgs = @("assembleDebug")
if ($ip) { $gradleArgs += "-PserverIp=$ip" } # default address and built-in certificate for this laptop
.\gradlew.bat @gradleArgs
Set-Location $root # leave the caller where they started
if ($LASTEXITCODE -ne 0) { throw "Build failed" }
$apk = "$root\android\app\build\outputs\apk\debug\app-debug.apk"
Write-Host "APK: $apk"
$sdk = (Get-Content android\local.properties | Where-Object { $_ -like "sdk.dir=*" }) -replace "^sdk.dir=", "" -replace "\\(.)", '$1'
$ErrorActionPreference = "Continue" # adb writes startup notes to stderr
$adb = Join-Path $sdk "platform-tools\adb.exe"
if ((Test-Path $adb) -and ((& $adb devices) -match "\tdevice$")) { & $adb install -r $apk }
else { Write-Host "No phone connected: copy the APK to the phone and open it to install." }
