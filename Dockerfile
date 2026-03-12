# ── Base Python image ────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# Set working directory inside the container
WORKDIR /app

# Install system dependencies needed for psycopg2 (PostgreSQL driver)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Install Python dependencies ──────────────────────────────────────────────
COPY requirements.txt .

# Install only production dependencies
RUN pip install --no-cache-dir flask flask-sqlalchemy flask-migrate \
    psycopg2-binary gunicorn

# ── Copy application source code ─────────────────────────────────────────────
COPY . .

# Expose the port Gunicorn will listen on
EXPOSE 5000

# Set environment defaults
ENV FLASK_APP=run.py
ENV FLASK_DEBUG=0

# Run database migrations then start Gunicorn with 3 worker processes
CMD ["sh", "-c", "flask db upgrade && gunicorn --bind 0.0.0.0:5000 --workers 3 run:app"]