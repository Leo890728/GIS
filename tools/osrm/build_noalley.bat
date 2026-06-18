@echo off
cd /d "%~dp0"

set PBF=taiwan-260527.osm.pbf
set OUT=taiwan-noalley.osrm
set IMAGE=ghcr.io/project-osrm/osrm-backend

echo [1/4] Extract with no-alley profile...
docker run --rm -v "%cd%:/data" %IMAGE% osrm-extract -p /data/car_no_alley.lua -o /data/%OUT% /data/%PBF%
if errorlevel 1 goto error

echo [2/4] Copy datasource_names (osrm-extract -o quirk)...
copy /Y "%~dp0taiwan-260527.osrm.datasource_names" "%~dp0taiwan-noalley.osrm.datasource_names" >nul
if errorlevel 1 ( echo WARNING: datasource_names copy failed, continuing... )

echo [3/4] Partition...
docker run --rm -v "%cd%:/data" %IMAGE% osrm-partition /data/%OUT%
if errorlevel 1 goto error

echo [4/4] Customize...
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
