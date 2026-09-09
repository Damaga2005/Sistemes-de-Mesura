param(
    [switch]$Dev
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$pyv = & python -c "import sys;print('%d.%d'%sys.version_info[:2])"
$maj, $min = $pyv.Split(".")
if ([int]$maj -ne 3 -or [int]$min -lt 11 -or [int]$min -ge 15) {
    throw "Se requiere Python >=3.11,<3.15 (encontrado $pyv)"
}

$venv = Join-Path $root ".venv"
if (-not (Test-Path $venv)) { & python -m venv $venv }
$py = Join-Path $venv "Scripts\python.exe"
& $py -m pip install --no-input --upgrade pip
if ($Dev) { & $py -m pip install --no-input -e "$root[dev]" }
else { & $py -m pip install --no-input $root }

$sistemes = Join-Path $venv "Scripts\sistemes.exe"
Write-Output ("CLI: " + $sistemes)
if ($Dev) {
    & $py -m pytest (Join-Path $root "tests") -q
    & $sistemes check
}
