# Builds dist\SistemesDeMesura.exe. Usage: .\build.ps1
$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $proj

$py = "python"
if (Test-Path ".\venv\Scripts\python.exe") { $py = ".\venv\Scripts\python.exe" }
elseif (Test-Path ".\.venv\Scripts\python.exe") { $py = ".\.venv\Scripts\python.exe" }

& $py -c "import webview, PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Missing desktop/build deps. Run:  $py -m pip install -e `".[desktop,build]`"" -ForegroundColor Red
    exit 1
}

if (Test-Path ".\build") { Remove-Item ".\build" -Recurse -Force }
if (Test-Path ".\dist")  { Remove-Item ".\dist"  -Recurse -Force }

& $py -m PyInstaller escritorio.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exe = ".\dist\SistemesDeMesura.exe"
if (-not (Test-Path $exe) -or (Get-Item $exe).Length -le 0) {
    Write-Host "Build finished but $exe is missing or empty" -ForegroundColor Red
    exit 1
}
Write-Host "OK: $((Get-Item $exe).FullName)  ($([math]::Round((Get-Item $exe).Length/1MB,1)) MB)" -ForegroundColor Green
