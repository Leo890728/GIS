# Single image used by both the web service and the capture worker (they only
# differ by the command run). See docker-compose.yml.
FROM python:3.12-slim

# mod_spatialite backs region/range GeoJSON (used by the web service; harmless
# and unused for the capture worker).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libsqlite3-mod-spatialite \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend

EXPOSE 5000

# Default command = web server. The capture worker overrides `command` in
# docker-compose.yml with `python -m backend.worker`.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "backend.app:create_app()"]
