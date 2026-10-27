$ErrorActionPreference = "Stop"

$desktop = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Split-Path -Parent $desktop
$staging = Join-Path $desktop "backend"
$dist = Join-Path $desktop "dist"

if (Test-Path $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force
}
New-Item -ItemType Directory -Path $staging | Out-Null

Copy-Item -LiteralPath (Join-Path $project "mailagent") -Destination $staging -Recurse
foreach ($asset in @("index.html", "app.js", "styles.css")) {
    Copy-Item -LiteralPath (Join-Path $project $asset) -Destination $staging
}

& (Join-Path $desktop "node_modules\\.bin\\electron-packager.cmd") $desktop "mailagent" `
    --platform=win32 --arch=x64 --out=$dist --overwrite --prune=true --asar `
    --extra-resource=$staging

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$portableRoot = Join-Path $dist "mailagent-win32-x64"
$archive = Join-Path $dist "mailagent-win32-x64-portable.zip"
if (Test-Path $archive) {
    Remove-Item -LiteralPath $archive -Force
}
Compress-Archive -Path (Join-Path $portableRoot "*") -DestinationPath $archive
