param(
    [string]$BindHost = $env:SM_HOST,
    [int]$Port = $(if ($env:SM_PORT) { [int]$env:SM_PORT } else { 8901 }),
    [string]$DataDir = $env:SM_DATA_DIR,
    [string]$Calendar = $env:COURSE_CALENDAR_PATH
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$arguments = @("-m", "web.server", "--host", ($BindHost | ForEach-Object {
    if ($_) { $_ } else { "127.0.0.1" }
}), "--port", $Port.ToString())
if ($DataDir) { $arguments += @("--data-dir", $DataDir) }
if ($Calendar) { $arguments += @("--calendar", $Calendar) }
Push-Location $root
try {
    & python $arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
