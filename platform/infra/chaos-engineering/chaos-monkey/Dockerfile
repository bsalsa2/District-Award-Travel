# Chaos Monkey Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY chaos-monkey/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY chaos-monkey/src /app/src
COPY chaos-monkey/config /app/config
COPY chaos-monkey/scripts /app/scripts

# Create logs directory
RUN mkdir -p /app/logs && chown -R nobody:nogroup /app/logs

# Switch to non-root user
USER nobody

# Expose metrics port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:9090/health || exit 1

# Entrypoint
ENTRYPOINT ["python", "-m", "src.main"]
