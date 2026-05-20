# Alerting service with logging and health checks
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for logs and health checks
RUN mkdir -p /var/log/alerting /var/run/alerting

# Set up health check script
COPY healthcheck.sh /usr/local/bin/healthcheck
RUN chmod +x /usr/local/bin/healthcheck

# Set up log rotation
COPY logrotate.conf /etc/logrotate.d/alerting

# Expose ports
EXPOSE 8080 8443

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
    CMD /usr/local/bin/healthcheck

# Entrypoint
CMD ["python", "main.py"]
