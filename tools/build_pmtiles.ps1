# Build PMTiles for stat_zone, stat_zone_1, stat_zone_2 from bounds.sqlite.
# Pipeline: ogr2ogr (GDAL Docker) → tippecanoe v2 (direct PMTiles output)
#
# Usage (from repo root):
#   .\tools\build_pmtiles.ps1             # full run
#   .\tools\build_pmtiles.ps1 -SkipExport # skip GeoJSON export if already done

param([switch]$SkipExport)

$ErrorActionPreference = "Stop"

$BOUNDS = "/workspace/backend/data/bounds.sqlite"
$TMP    = "backend/tmp"
$OUT    = "backend/pmtiles"

$layers = @(
    @{ name="stat_zone";   minz=12; maxz=14 },
    @{ name="stat_zone_1"; minz=11; maxz=13 },
    @{ name="stat_zone_2"; minz=9;  maxz=12 }
)

function Assert-LastExitCode($msg) {
    if ($LASTEXITCODE -ne 0) { throw "$msg (exit $LASTEXITCODE)" }
}

# ── Step 1: Export GeoJSON ────────────────────────────────────────────────────
if ($SkipExport) {
    Write-Host "=== [1/2] Skipping GeoJSON export ===" -ForegroundColor DarkGray
} else {
    Write-Host "=== [1/2] Exporting GeoJSON from bounds.sqlite ===" -ForegroundColor Cyan

    $exportCmds = ($layers | ForEach-Object {
        "ogr2ogr -f GeoJSON /workspace/$TMP/$($_.name).geojson $BOUNDS $($_.name)"
    }) -join " && "

    docker run --rm -v "${PWD}:/workspace" ghcr.io/osgeo/gdal:alpine-normal-latest `
        sh -c $exportCmds
    Assert-LastExitCode "GeoJSON export failed"
    Write-Host "GeoJSON export done." -ForegroundColor Green
}

# ── Step 2: tippecanoe v2 → PMTiles (direct) ─────────────────────────────────
foreach ($layer in $layers) {
    $name = $layer.name
    $minz = $layer.minz
    $maxz = $layer.maxz

    Write-Host "=== [2/2] tippecanoe: $name (zoom $minz-$maxz) ===" -ForegroundColor Cyan

    docker run --rm -v "${PWD}:/workspace" ghcr.io/leo890728/tippecanoe:latest `
        -o /workspace/$OUT/$name.pmtiles `
        -Z $minz -z $maxz `
        --layer=$name `
        --force `
        --coalesce-densest-as-needed `
        --extend-zooms-if-still-dropping `
        --detect-shared-borders `
        /workspace/$TMP/$name.geojson
    Assert-LastExitCode "tippecanoe failed for $name"

    Write-Host "$name done." -ForegroundColor Green
}

Write-Host "=== Done ===" -ForegroundColor Cyan
Get-Item backend\pmtiles\stat_zone*.pmtiles | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}
