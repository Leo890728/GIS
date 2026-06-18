#!/bin/sh
# Download all boundary SHP files into /workspace/backend/shp/
# Run inside Docker GDAL: called by tools/init.ps1
# Skip layers that already have a .shp file present.
set -e

apk add --no-cache curl unzip -q 2>/dev/null || true

SHP="/workspace/backend/shp"

download_layer() {
  name="$1"
  dir="$2"
  url="$3"

  mkdir -p "$SHP/$dir"
  if ls "$SHP/$dir"/*.shp > /dev/null 2>&1; then
    echo "[$name] Already downloaded, skipping."
    return
  fi
  echo "[$name] Downloading..."
  curl -fsSL --retry 3 -o "$SHP/$dir/download.zip" "$url"
  unzip -o "$SHP/$dir/download.zip" -d "$SHP/$dir/"
  rm -f "$SHP/$dir/download.zip"
  echo "[$name] Done."
}

# 縣市界 (TWD97 lat/lon → no reprojection needed)
download_layer "county" "county" \
  "https://www.tgos.tw/tgos/VirtualDir/Product/1cd4f4c9-6b01-4cf9-bf6c-23a73aa17d24/%E7%9B%B4%E8%BD%84%E5%B8%82%E3%80%81%E7%B8%A3(%E5%B8%82)%E7%95%8C%E7%B7%9A1140318.zip"

# 鄉鎮市區界
download_layer "township" "township" \
  "https://www.tgos.tw/tgos/VirtualDir/Product/3fe61d4a-ca23-4f45-8aca-4a536f40f290/%E9%84%89(%E9%8E%AE%E3%80%81%E5%B8%82%E3%80%81%E5%8D%80)%E7%95%8C%E7%B7%9A1140318.zip"

# 村里界
download_layer "village" "village" \
  "https://www.tgos.tw/tgos/VirtualDir/Product/a04697c8-64db-450a-a105-3eb471c45abd/%E6%9D%91(%E9%87%8C)%E7%95%8C(TWD97%E7%B6%93%E7%B7%AF%E5%BA%A6)1150511.zip"

# 二級發布區 (BIG5, EPSG:3826)
download_layer "stat_zone_2" "stat_zone_2" \
  "https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/38C0F19D-843A-46F1-9B93-7393A83A1920/resource/F3B9120C-F312-42EB-A5CB-EDFC1CC41B47/download"

# 一級發布區 (BIG5, EPSG:3826)
download_layer "stat_zone_1" "stat_zone_1" \
  "https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/46F3CC1B-A51E-4C26-8C5A-74449E1299AE/resource/D3CB08BA-001D-4FFE-9FA4-7F2FA4B758FA/download"

# 最小統計區 — 無公開下載，請手動放置 SHP 至 backend/shp/stat_zone/
if ls "$SHP/stat_zone"/*.shp > /dev/null 2>&1; then
  echo "[stat_zone] Found."
else
  echo "[stat_zone] WARNING: 無公開下載，請手動將 SHP 放置於 backend/shp/stat_zone/"
fi

echo "=== Download complete ==="
