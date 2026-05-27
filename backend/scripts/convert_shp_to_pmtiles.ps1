param(
  [Parameter(Mandatory = $true)]
  [string]$InputShp,

  [Parameter(Mandatory = $true)]
  [string]$DatasetId,

  [string]$DatasetName = "113年統計區常用資料集-最小統計區",
  [int]$SourceEpsg = 3826,
  [int]$TargetEpsg = 4326,
  [string]$BackendDir = "backend"
)

$ErrorActionPreference = "Stop"

function Assert-CommandExists {
  param([string]$CommandName)
  if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
    throw "找不到指令: $CommandName"
  }
}

Assert-CommandExists "docker"

$repoRoot = (Get-Location).Path
$backendPath = Join-Path $repoRoot $BackendDir
$inputPath = Join-Path $repoRoot $InputShp

if (-not (Test-Path $inputPath)) {
  throw "找不到 SHP: $inputPath"
}

$pmtilesExe = Join-Path $repoRoot "tools/pmtiles/pmtiles.exe"
if (-not (Test-Path $pmtilesExe)) {
  throw "找不到 pmtiles.exe: $pmtilesExe"
}

$geojsonDir = Join-Path $backendPath ("geojson/" + $DatasetId)
$mbtilesDir = Join-Path $backendPath "mbtiles"
$pmtilesDir = Join-Path $backendPath "pmtiles"

New-Item -ItemType Directory -Force -Path $geojsonDir | Out-Null
New-Item -ItemType Directory -Force -Path $mbtilesDir | Out-Null
New-Item -ItemType Directory -Force -Path $pmtilesDir | Out-Null

$geojsonPath = Join-Path $geojsonDir ($DatasetId + ".geojson")
$mbtilesPath = Join-Path $mbtilesDir ($DatasetId + ".mbtiles")
$pmtilesPath = Join-Path $pmtilesDir ($DatasetId + ".pmtiles")
$metaPath = Join-Path $geojsonDir ($DatasetId + ".meta.json")

$shpDir = Split-Path -Path $inputPath -Parent
$shpName = Split-Path -Path $inputPath -Leaf

Write-Host "[$DatasetId] SHP -> GeoJSON"
docker run --rm -v "${shpDir}:/data" ghcr.io/osgeo/gdal:alpine-normal-latest `
  ogr2ogr -s_srs "EPSG:$SourceEpsg" -t_srs "EPSG:$TargetEpsg" -f GeoJSON "/data/out.geojson" "/data/$shpName"

Copy-Item -Force -Path (Join-Path $shpDir "out.geojson") -Destination $geojsonPath

Write-Host "[$DatasetId] GeoJSON -> MBTiles"
docker run --rm -v "${repoRoot}:/work" klokantech/tippecanoe:latest `
  tippecanoe -f -o "/work/$BackendDir/mbtiles/$DatasetId.mbtiles" -zg --drop-densest-as-needed "/work/$BackendDir/geojson/$DatasetId/$DatasetId.geojson"

Write-Host "[$DatasetId] MBTiles -> PMTiles"
& $pmtilesExe convert $mbtilesPath $pmtilesPath

$meta = [ordered]@{
  datasetId = $DatasetId
  datasetName = $DatasetName
  sourceShp = $InputShp
  sourceEpsg = $SourceEpsg
  targetEpsg = $TargetEpsg
  generatedAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
  outputs = @{
    geojson = "backend/geojson/$DatasetId/$DatasetId.geojson"
    mbtiles = "backend/mbtiles/$DatasetId.mbtiles"
    pmtiles = "backend/pmtiles/$DatasetId.pmtiles"
  }
}

$meta | ConvertTo-Json -Depth 5 | Set-Content -Path $metaPath -Encoding UTF8

Write-Host ""
Write-Host "完成:"
Write-Host "  $geojsonPath"
Write-Host "  $mbtilesPath"
Write-Host "  $pmtilesPath"
Write-Host "  $metaPath"

