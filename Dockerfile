# Shared image for both the bot and the web dashboard.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application.
COPY . .

# Data (SQLite + uploads) lives on a mounted volume.
RUN mkdir -p /app/data/uploads

# Default command is overridden per-service in docker-compose.yml.
CMD ["python", "run_web.py"]
