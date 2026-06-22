@echo off
cd /d "%~dp0"

for /f "delims=" %%f in ('dir /b /o-d taiwan-*.osm.pbf') do (
    set "PBF=%%f"
    goto found
)

echo No taiwan-*.osm.pbf found.
pause
exit /b 1

:found
set "OUT=taiwan.osrm"
set IMAGE=ghcr.io/project-osrm/osrm-backend

echo PBF=%PBF%
echo OUT=%OUT%

echo [1/3] Extract with default car profile...
docker run --rm -v "%cd%:/data" %IMAGE% osrm-extract -p /opt/car.lua -o /data/%OUT% /data/%PBF%
if errorlevel 1 goto error

echo [2/3] Partition...
docker run --rm -v "%cd%:/data" %IMAGE% osrm-partition /data/%OUT%
if errorlevel 1 goto error

echo [3/3] Customize...
docker run --rm -v "%cd%:/data" %IMAGE% osrm-customize /data/%OUT%
if errorlevel 1 goto error

echo.
echo Build complete: %OUT%
pause
exit /b 0

:error
echo.
echo Build FAILED at the step above.
pause
exit /b 1