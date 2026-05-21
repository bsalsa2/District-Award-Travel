# Chaos Dashboard Dockerfile
FROM node:18-alpine

# Install dependencies
RUN apk add --no-cache \
    git \
    curl \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Copy package files
COPY chaos-dashboard/package.json .
COPY chaos-dashboard/package-lock.json .

# Install Node.js dependencies
RUN npm ci --only=production

# Copy application code
COPY chaos-dashboard/src /app/src
COPY chaos-dashboard/public /app/public
COPY chaos-dashboard/views /app/views

# Create logs directory
RUN mkdir -p /app/logs && chown -R node:node /app/logs

# Switch to non-root user
USER node

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8080/health || exit 1

# Entrypoint
ENTRYPOINT ["node", "src/server.js"]
