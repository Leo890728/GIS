# Download required binary tools for local development.
# Run once from repo root: .\tools\setup.ps1
#
# Downloads:
#   tools/pmtiles/pmtiles.exe        — PMTiles CLI (protomaps/go-pmtiles)
#   tools/spatialite/mod_spatialite* — SpatiaLite extension for Windows

$ErrorActionPreference = "Stop"

$PMTILES_VERSION = "3.3.1"
$SPATIALITE_VERSION = "5.1.0"

function Download-File($url, $dest) {
    Write-Host "  Downloading $(Split-Path $dest -Leaf)..."
    Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
}

# ── pmtiles.exe ───────────────────────────────────────────────────────────────
$pmtilesDir = "tools\pmtiles"
$pmtilesExe = "$pmtilesDir\pmtiles.exe"

if (Test-Path $pmtilesExe) {
    Write-Host "[pmtiles] Already exists, skipping." -ForegroundColor DarkGray
} else {
    New-Item -ItemType Directory -Force $pmtilesDir | Out-Null
    Write-Host "[pmtiles] Downloading v$PMTILES_VERSION..." -ForegroundColor Cyan
    $url = "https://github.com/protomaps/go-pmtiles/releases/download/v$PMTILES_VERSION/go-pmtiles_${PMTILES_VERSION}_Windows_x86_64.zip"
    $zip = "$env:TEMP\pmtiles.zip"
    Download-File $url $zip
    Expand-Archive -Path $zip -DestinationPath $pmtilesDir -Force
    Remove-Item $zip
    Write-Host "[pmtiles] Done -> $pmtilesExe" -ForegroundColor Green
}

# ── SpatiaLite (mod_spatialite.dll) ──────────────────────────────────────────
$spatialiteDir = "tools\spatialite"
$spatialiteDll = "$spatialiteDir\mod_spatialite.dll"

if (Test-Path $spatialiteDll) {
    Write-Host "[spatialite] Already exists, skipping." -ForegroundColor DarkGray
} else {
    New-Item -ItemType Directory -Force $spatialiteDir | Out-Null
    Write-Host "[spatialite] Downloading v$SPATIALITE_VERSION (win-amd64)..." -ForegroundColor Cyan
    $url = "https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/mod_spatialite-$SPATIALITE_VERSION-win-amd64.7z"
    $archive = "$env:TEMP\mod_spatialite.7z"
    Download-File $url $archive

    # 7-Zip required — try system 7z first, then Docker
    $sevenZip = (Get-Command "7z" -ErrorAction SilentlyContinue)?.Source
    if ($sevenZip) {
        & $sevenZip x $archive -o"$spatialiteDir" -y | Out-Null
    } else {
        Write-Warning "7z not found — install 7-Zip or extract $archive manually into $spatialiteDir"
    }
    Remove-Item $archive -ErrorAction SilentlyContinue
    Write-Host "[spatialite] Done -> $spatialiteDll" -ForegroundColor Green
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Cyan
Write-Host "  pmtiles : $pmtilesExe"
Write-Host "  spatialite : $spatialiteDll"
