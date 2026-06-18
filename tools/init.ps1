# Full initialization pipeline for a fresh clone.
# Requires: Docker (running), internet access
#
# Usage (from repo root):
#   .\tools\init.ps1                   # build everything from source
#   .\tools\init.ps1 -FromRelease      # download pre-built assets from GitHub Release (no Docker needed)
#   .\tools\init.ps1 -SkipDownload     # SHP already in backend/shp/
#   .\tools\init.ps1 -SkipImport       # bounds.sqlite already built
#   .\tools\init.ps1 -SkipPmtiles      # PMTiles already built

param(
    [switch]$FromRelease,
    [switch]$SkipTools,
    [switch]$SkipDownload,
    [switch]$SkipImport,
    [switch]$SkipPmtiles
)

$ErrorActionPreference = "Stop"
$REPO = "Leo890728/GIS"

function Step($n, $total, $label) {
    Write-Host ""
    Write-Host "=== [$n/$total] $label ===" -ForegroundColor Cyan
}

function Assert-Exit($msg) {
    if ($LASTEXITCODE -ne 0) { throw "$msg (exit $LASTEXITCODE)" }
}

function Assert-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker not found. Please install Docker Desktop."
    }
    docker info > $null 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Docker is not running." }
}

function Expand-Gz($src, $dst) {
    $inputStream  = [System.IO.File]::OpenRead($src)
    $outputStream = [System.IO.File]::Create($dst)
    $gzStream     = [System.IO.Compression.GZipStream]::new($inputStream, [System.IO.Compression.CompressionMode]::Decompress)
    $gzStream.CopyTo($outputStream)
    $gzStream.Dispose(); $outputStream.Dispose(); $inputStream.Dispose()
}

# ══════════════════════════════════════════════════════════════════════════════
# MODE A: Download pre-built assets from GitHub Release
# ══════════════════════════════════════════════════════════════════════════════
if ($FromRelease) {
    Write-Host ""
    Write-Host "=== Downloading pre-built assets from GitHub Release ===" -ForegroundColor Cyan

    # Fetch latest release metadata
    $api      = "https://api.github.com/repos/$REPO/releases/latest"
    $headers  = @{ "User-Agent" = "init.ps1" }
    $release  = Invoke-RestMethod -Uri $api -Headers $headers
    $tag      = $release.tag_name
    Write-Host "Release: $tag" -ForegroundColor DarkGray

    New-Item -ItemType Directory -Force backend\data    | Out-Null
    New-Item -ItemType Directory -Force backend\pmtiles | Out-Null
    New-Item -ItemType Directory -Force backend\tmp     | Out-Null

    foreach ($asset in $release.assets) {
        $name = $asset.name
        $url  = $asset.browser_download_url
        $mb   = [math]::Round($asset.size / 1MB, 1)

        if ($name -like "*.sqlite.gz") {
            $dst = "backend\tmp\$name"
            Write-Host "  Downloading $name (${mb} MB)..."
            Invoke-WebRequest -Uri $url -OutFile $dst -UseBasicParsing
            $outName = $name -replace '\.gz$', ''
            Write-Host "  Decompressing → backend\data\$outName ..."
            Expand-Gz $dst "backend\data\$outName"
            Remove-Item $dst

        } elseif ($name -like "*.pmtiles") {
            Write-Host "  Downloading $name (${mb} MB)..."
            Invoke-WebRequest -Uri $url -OutFile "backend\pmtiles\$name" -UseBasicParsing
        }
    }

    # Setup pmtiles.exe (still needed for tile serving)
    if (-not (Test-Path "tools\pmtiles\pmtiles.exe")) {
        Write-Host ""
        Write-Host "  Setting up tools..." -ForegroundColor DarkGray
        & .\tools\setup.ps1
    }

    Write-Host ""
    Write-Host "=== Done ===" -ForegroundColor Green
    Write-Host "Next: python -m backend.app" -ForegroundColor DarkGray
    exit 0
}

# ══════════════════════════════════════════════════════════════════════════════
# MODE B: Build from source
# ══════════════════════════════════════════════════════════════════════════════
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
    docker run --rm -v "${PWD}:/workspace" $GDAL sh -c "tr -d '\015' < /workspace/tools/docker/download_shp.sh | sh"
    Assert-Exit "download_shp.sh failed"
}

# ── [3] Import SHP → bounds.sqlite ───────────────────────────────────────────
Step 3 $TOTAL "Import SHP → bounds.sqlite + precomputed tables"

if ($SkipImport) {
    Write-Host "Skipped." -ForegroundColor DarkGray
} else {
    New-Item -ItemType Directory -Force backend\data | Out-Null

    docker run --rm -v "${PWD}:/workspace" $GDAL sh -c "tr -d '\015' < /workspace/tools/docker/import_bounds.sh | sh"
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
