# Package backend/data/*.sqlite and backend/pmtiles/*.pmtiles as GitHub Release assets.
# Requires: gh CLI (winget install GitHub.cli), authenticated (gh auth login)
#
# Usage (from repo root):
#   .\tools\publish_release.ps1                    # tag = data-YYYYMMDD
#   .\tools\publish_release.ps1 -Tag data-20260618

param([string]$Tag = "data-$(Get-Date -Format 'yyyyMMdd')")

$ErrorActionPreference = "Stop"

# ── Prerequisites ─────────────────────────────────────────────────────────────
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "gh CLI not found. Installing via winget..." -ForegroundColor Yellow
    winget install -e --id GitHub.cli --silent
    $env:PATH += ";$env:LOCALAPPDATA\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source\tools"
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "Please restart your terminal after gh CLI installation, then re-run."
    }
}

gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Not authenticated. Run: gh auth login" }

# ── Compress SQLite files ─────────────────────────────────────────────────────
$TMP = "backend\tmp\release"
New-Item -ItemType Directory -Force $TMP | Out-Null

$sqliteFiles = @("backend\data\bounds.sqlite", "backend\data\data.sqlite")
$assets = @()

foreach ($src in $sqliteFiles) {
    if (-not (Test-Path $src)) { Write-Warning "$src not found, skipping."; continue }
    $name = [System.IO.Path]::GetFileName($src) + ".gz"
    $dst  = "$TMP\$name"
    Write-Host "Compressing $src → $dst ..."
    $inputStream  = [System.IO.File]::OpenRead($src)
    $outputStream = [System.IO.File]::Create($dst)
    $gzStream     = [System.IO.Compression.GZipStream]::new($outputStream, [System.IO.Compression.CompressionLevel]::Optimal)
    $inputStream.CopyTo($gzStream)
    $gzStream.Dispose(); $outputStream.Dispose(); $inputStream.Dispose()
    $mb = [math]::Round((Get-Item $dst).Length / 1MB, 1)
    Write-Host "  → ${mb} MB" -ForegroundColor Green
    $assets += $dst
}

# ── Collect PMTiles ───────────────────────────────────────────────────────────
Get-Item backend\pmtiles\*.pmtiles -ErrorAction SilentlyContinue | ForEach-Object {
    $assets += $_.FullName
}

if ($assets.Count -eq 0) { throw "No assets to upload." }

Write-Host ""
Write-Host "Assets to upload:" -ForegroundColor Cyan
$assets | ForEach-Object {
    Write-Host ("  {0,-40} {1} MB" -f [System.IO.Path]::GetFileName($_), [math]::Round((Get-Item $_).Length/1MB,1))
}

# ── Create release + upload ───────────────────────────────────────────────────
Write-Host ""
Write-Host "Creating release $Tag ..." -ForegroundColor Cyan

$notes = "Pre-built data assets for Leo890728/GIS.`n`nContents:`n"
$notes += "- bounds.sqlite.gz  (SpatiaLite: county/township/village/stat_zone + precomputed cache)`n"
$notes += "- data.sqlite.gz    (stat_zone_stats_113 + column_labels)`n"
$notes += "- *.pmtiles         (vector tiles for all boundary layers)"

gh release create $Tag --title "Data $Tag" --notes $notes @assets
if ($LASTEXITCODE -ne 0) { throw "gh release create failed" }

# ── Cleanup ───────────────────────────────────────────────────────────────────
Remove-Item $TMP -Recurse -Force

Write-Host ""
Write-Host "Published: https://github.com/Leo890728/GIS/releases/tag/$Tag" -ForegroundColor Green
