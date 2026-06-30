# Single image used by both the web service and the capture worker (they only
# differ by the command run). See docker-compose.yml.
FROM python:3.12-slim

# mod_spatialite backs region/range GeoJSON; the go-pmtiles CLI extracts vector
# tiles from .pmtiles archives (the Windows pmtiles.exe can't run here).
ARG PMTILES_VERSION=1.30.3
RUN apt-get update \
 && apt-get install -y --no-install-recommends libsqlite3-mod-spatialite curl ca-certificates \
 && curl -fsSL "https://github.com/protomaps/go-pmtiles/releases/download/v${PMTILES_VERSION}/go-pmtiles_${PMTILES_VERSION}_Linux_x86_64.tar.gz" \
    | tar -xz -C /usr/local/bin pmtiles \
 && chmod +x /usr/local/bin/pmtiles \
 && apt-get purge -y --auto-remove curl \
 && rm -rf /var/lib/apt/lists/*
ENV PMTILES_BIN=/usr/local/bin/pmtiles

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend

EXPOSE 5000

# Default command = web server. The capture worker overrides `command` in
# docker-compose.yml with `python -m backend.worker`.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "backend.app:create_app()"]
