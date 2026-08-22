FROM python:3.11-slim

# renderer.py hardcodes /usr/share/fonts/truetype/dejavu/
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/

# Reference only. Not read at runtime: the real config.json lives on the
# Fly volume at $STRAVA_CONFIG_DIR (/data), see fly.toml [mounts].
COPY config.example.json .

# WORKDIR is /app/server so `app.py` can import its siblings (aggregator,
# renderer, ...) as top-level modules. It no longer determines where
# config.json is found; STRAVA_CONFIG_DIR does that.
WORKDIR /app/server
ENV PYTHONPATH=/app/server

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
