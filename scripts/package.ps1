param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\dist")
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$output = [IO.Path]::GetFullPath($OutputDir)
$temp = Join-Path ([IO.Path]::GetTempPath()) (
    "sistemes-package-" + [guid]::NewGuid().ToString("N"))
$stage = Join-Path $temp "sistemes-de-mesura"
$version = "0.13.0"
$artifact = Join-Path $output ("sistemes-de-mesura-" + $version + "-portable.zip")

New-Item -ItemType Directory -Path $stage -Force | Out-Null
try {
    foreach ($item in @("app", "data", "docs", "web", "pyproject.toml",
                        ".env.example", "AGENTS.md")) {
        Copy-Item -LiteralPath (Join-Path $repo $item) -Destination $stage `
            -Recurse -Force
    }
    New-Item -ItemType Directory -Path (Join-Path $stage "scripts") -Force |
        Out-Null
    Copy-Item -LiteralPath (Join-Path $repo "scripts\run-web.ps1") `
        -Destination (Join-Path $stage "scripts\run-web.ps1") -Force

    $manifest = Get-ChildItem -LiteralPath $stage -File -Recurse |
        ForEach-Object {
            [ordered]@{
                path = $_.FullName.Substring($stage.Length + 1).Replace("\", "/")
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            }
        }
    $manifest | ConvertTo-Json -Depth 3 |
        Set-Content -LiteralPath (Join-Path $stage "PACKAGE-MANIFEST.json") `
        -Encoding UTF8

    New-Item -ItemType Directory -Path $output -Force | Out-Null
    Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $artifact `
        -CompressionLevel Optimal -Force
    $hash = Get-FileHash -LiteralPath $artifact -Algorithm SHA256
    Write-Output ("ARTIFACT: " + $artifact)
    Write-Output ("SHA256: " + $hash.Hash)
}
finally {
    if (Test-Path -LiteralPath $temp) {
        Remove-Item -LiteralPath $temp -Recurse -Force
    }
}
