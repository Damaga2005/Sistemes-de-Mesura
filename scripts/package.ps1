param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\dist")
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$output = [IO.Path]::GetFullPath($OutputDir)
$temp = Join-Path ([IO.Path]::GetTempPath()) (
    "sistemes-package-" + [guid]::NewGuid().ToString("N"))
$stage = Join-Path $temp "sistemes-de-mesura"
$pyproject = Get-Content -LiteralPath (Join-Path $repo "pyproject.toml") -Raw
$version = [regex]::Match($pyproject, 'version\s*=\s*"([^"]+)"').Groups[1].Value
$artifact = Join-Path $output ("sistemes-de-mesura-" + $version + "-portable.zip")

New-Item -ItemType Directory -Path $stage -Force | Out-Null
try {
    foreach ($item in @("app", "data", "docs", "web", "pyproject.toml",
                        ".env.example", "AGENTS.md", "CHANGELOG.md")) {
        Copy-Item -LiteralPath (Join-Path $repo $item) -Destination $stage `
            -Recurse -Force
    }
    New-Item -ItemType Directory -Path (Join-Path $stage "scripts") -Force |
        Out-Null
    Copy-Item -LiteralPath (Join-Path $repo "scripts\run-web.ps1") `
        -Destination (Join-Path $stage "scripts\run-web.ps1") -Force
    Copy-Item -LiteralPath (Join-Path $repo "scripts\install.ps1") `
        -Destination (Join-Path $stage "scripts\install.ps1") -Force
    & python -c "import sys; sys.path.insert(0, r'$stage'); from app.artifacts import write_manifest; print(write_manifest())"
    $manifestPath = Join-Path $stage "data\ARTIFACT-MANIFEST.json"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "falta data\ARTIFACT-MANIFEST.json en el stage"
    }

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
