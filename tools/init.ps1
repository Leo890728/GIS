# Full initialization pipeline for a fresh clone.
# Requires: Docker (running), internet access
#
# Usage (from repo root):
#   .\tools\init.ps1
#   .\tools\init.ps1 -SkipDownload    # SHP already in backend/shp/
#   .\tools\init.ps1 -SkipImport      # bounds.sqlite already built
#   .\tools\init.ps1 -SkipPmtiles     # PMTiles already built

param(
    [switch]$SkipTools,
    [switch]$SkipDownload,
    [switch]$SkipImport,
    [switch]$SkipPmtiles
)

$ErrorActionPreference = "Stop"

function Step($n, $total, $label) {
    Write-Host ""
    Write-Host "=== [$n/$total] $label ===" -ForegroundColor Cyan
}

function Assert-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker not found. Please install Docker Desktop."
    }
    docker info > $null 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Docker is not running." }
}

function Assert-Exit($msg) {
    if ($LASTEXITCODE -ne 0) { throw "$msg (exit $LASTEXITCODE)" }
}

$GDAL       = "ghcr.io/osgeo/gdal:alpine-normal-latest"
$TIPPECANOE = "ghcr.io/leo890728/tippecanoe:latest"
$TOTAL      = 5

Assert-Docker

# ── [1] Setup tools ───────────────────────────────────────────────────────────
Step 1 $TOTAL "Setup tools (pmtiles.exe, spatialite)"

if ($SkipTools) {
    Write-Host "Skipped." -ForegroundColor DarkGray
} else {
    & .\tools\setup.ps1
    Assert-Exit "setup.ps1 failed"
}

# ── [2] Download SHP files ────────────────────────────────────────────────────
Step 2 $TOTAL "Download SHP files"

if ($SkipDownload) {
    Write-Host "Skipped." -ForegroundColor DarkGray
} else {
    New-Item -ItemType Directory -Force backend\shp | Out-Null
    docker run --rm -v "${PWD}:/workspace" $GDAL sh /workspace/tools/docker/download_shp.sh
    Assert-Exit "download_shp.sh failed"
}

# ── [3] Import SHP → bounds.sqlite ───────────────────────────────────────────
Step 3 $TOTAL "Import SHP → bounds.sqlite + precomputed tables"

if ($SkipImport) {
    Write-Host "Skipped." -ForegroundColor DarkGray
} else {
    New-Item -ItemType Directory -Force backend\data | Out-Null

    docker run --rm -v "${PWD}:/workspace" $GDAL sh /workspace/tools/docker/import_bounds.sh
    Assert-Exit "import_bounds.sh failed"

    Write-Host "Building precomputed tables..." -ForegroundColor DarkGray
    docker run --rm -v "${PWD}:/workspace" $GDAL python /workspace/tools/docker/build_bounds_extras.py
    Assert-Exit "build_bounds_extras.py failed"
}

# ── [4] Pull tippecanoe image ─────────────────────────────────────────────────
Step 4 $TOTAL "Pull tippecanoe image"

if ($SkipPmtiles) {
    Write-Host "Skipped." -ForegroundColor DarkGray
} else {
    $localImage = docker images -q tippecanoe:v2 2>$null
    if (-not $localImage) {
        Write-Host "Pulling $TIPPECANOE ..."
        docker pull $TIPPECANOE
        Assert-Exit "docker pull tippecanoe failed"
        docker tag $TIPPECANOE tippecanoe:v2
    } else {
        Write-Host "Image ready." -ForegroundColor DarkGray
    }
}

# ── [5] Build PMTiles ─────────────────────────────────────────────────────────
Step 5 $TOTAL "Build PMTiles"

if ($SkipPmtiles) {
    Write-Host "Skipped." -ForegroundColor DarkGray
} else {
    & .\tools\build_pmtiles.ps1
    Assert-Exit "build_pmtiles.ps1 failed"
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Init complete ===" -ForegroundColor Green
Write-Host ""

if (Test-Path backend\data\bounds.sqlite) {
    $sz = [math]::Round((Get-Item backend\data\bounds.sqlite).Length / 1MB, 1)
    Write-Host "  bounds.sqlite      : ${sz} MB"
}

Get-Item backend\pmtiles\*.pmtiles -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host ("  {0,-26}: {1} MB" -f $_.Name, [math]::Round($_.Length/1MB,1))
}

Write-Host ""
Write-Host "Next: python -m backend.app" -ForegroundColor DarkGray
