# Dockerfile for Cloud Run Translation Service
# Uses python:3.11-slim as base image for optimal performance and security

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install minimal system dependencies for document processing
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Cloud Run automatically sets PORT environment variable (default 8080)
# Use environment variable to avoid port conflicts
EXPOSE 8080

# Use gunicorn with environment variable for port
# exec ensures proper signal handling
CMD exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 1 --timeout 3600 --graceful-timeout 30 --max-requests 1 --max-requests-jitter 0 --access-logfile - --error-logfile - main:app