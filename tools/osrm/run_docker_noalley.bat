@echo off
cd /d "%~dp0"

docker run -t -i ^
-p 5002:5000 ^
-v "%cd%:/data" ^
ghcr.io/project-osrm/osrm-backend ^
osrm-routed ^
--algorithm mld ^
--max-table-size 1500 ^
/data/taiwan-noalley.osrm

pause
