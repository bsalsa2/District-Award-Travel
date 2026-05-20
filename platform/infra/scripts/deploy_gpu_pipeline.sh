#!/bin/bash
set -e

# District Award Travel - GPU CI/CD Pipeline Deployment Script
# Usage: ./deploy_gpu_pipeline.sh [--force] [--region us-east-1|eu-west-1|ap-southeast-1]

# Configuration
REGION="${1:-us-east-1}"
FORCE_REBUILD=false
DOCKER_REGISTRY="district-award"
GPU_COUNT=$(nvidia-smi -L | wc -l)

echo "🚀 Starting GPU CI/CD Pipeline Deployment for District Award Travel"
echo "Region: $REGION"
echo "GPU Count: $GPU_COUNT"
echo "Docker Registry: $DOCKER_REGISTRY"

# Validate GPU availability
if [ "$GPU_COUNT" -eq 0 ]; then
    echo "❌ No GPUs detected! This pipeline requires NVIDIA GPUs."
    exit 1
fi

# Validate Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found! Please install Docker."
    exit 1
fi

# Validate Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found! Please install Docker Compose."
    exit 1
fi

# Build custom images if needed
if [ "$FORCE_REBUILD" = true ] || [ ! "$(docker images -q ${DOCKER_REGISTRY}/canary-service:latest 2> /dev/null)" ]; then
    echo "🔨 Building custom GPU service images..."
    docker build -t ${DOCKER_REGISTRY}/canary-service:latest -f docker/canary/Dockerfile .
    docker build -t ${DOCKER_REGISTRY}/rollback-service:latest -f docker/rollback/Dockerfile .
    docker build -t ${DOCKER_REGISTRY}/region-sync:latest -f docker/sync/Dockerfile .
    docker push ${DOCKER_REGISTRY}/canary-service:latest
    docker push ${DOCKER_REGISTRY}/rollback-service:latest
    docker push ${DOCKER_REGISTRY}/region-sync:latest
fi

# Create required directories
mkdir -p certs logs/{nginx,morpheus,canary,rollback,sync,prometheus} \
         prometheus/data \
         grafana/provisioning/{dashboards,datasources} \
         jenkins \
         models \
         data \
         sync/config \
         canary/config \
         rollback/config

# Generate self-signed certificates for HTTPS
if [ ! -f certs/server.crt ]; then
    echo "🔐 Generating SSL certificates..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout certs/server.key -out certs/server.crt \
        -subj "/C=US/ST=California/L=San Francisco/O=District Award Travel/CN=districtaward.travel"
fi

# Configure Nginx
cat > nginx/conf.d/gpu-pipeline.conf << 'EOF'
upstream jenkins {
    server jenkins:8080;
}

upstream canary {
    server canary-service:8082;
}

upstream rollback {
    server rollback-service:8083;
}

upstream morpheus {
    server morpheus:8081;
}

upstream prometheus {
    server prometheus:9090;
}

upstream grafana {
    server grafana:3000;
}
EOF

# Configure Prometheus
cat > prometheus/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - '/etc/prometheus/alert.rules'

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'jenkins'
    metrics_path: '/jenkins/prometheus'
    static_configs:
      - targets: ['jenkins:8080']

  - job_name: 'morpheus'
    static_configs:
      - targets: ['morpheus:8081']

  - job_name: 'canary'
    static_configs:
      - targets: ['canary-service:8082']

  - job_name: 'rollback'
    static_configs:
      - targets: ['rollback-service:8083']

  - job_name: 'region-sync'
    static_configs:
      - targets: ['region-sync:8084']

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx-lb:9090']

  - job_name: 'gpu-workers'
    static_configs:
      - targets: ['gpu-worker-1:9100', 'gpu-worker-2:9100']
EOF

# Configure Grafana
cat > grafana/provisioning/datasources/datasources.yaml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
EOF

cat > grafana/provisioning/dashboards/dashboard.yaml << EOF
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: true
EOF

# Configure Morpheus
mkdir -p morpheus/config
cat > morpheus/config/morpheus.yaml << EOF
pipeline:
  name: "gpu-deployment-anomaly-detection"
  model:
    name: "bert-base-uncased"
    type: "nlp"
  input:
    source: "logs/deployment.logs"
    format: "json"
  output:
    destination: "logs/anomalies.json"
    format: "json"
  monitoring:
    metrics_port: 8081
    health_port: 8081
  gpu:
    enabled: true
    device: 0
EOF

# Configure Canary Service
cat > canary/config/config.yaml << EOF
deployment:
  regions:
    - name: "us-east-1"
      weight: 100
    - name: "eu-west-1"
      weight: 0
    - name: "ap-southeast-1"
      weight: 0
  health_check:
    endpoint: "/health"
    timeout: 5
    interval: 30
  rollback:
    enabled: true
    threshold: 5
    duration: 300
  monitoring:
    prometheus_port: 8082
    health_port: 8082
EOF

# Configure Rollback Service
cat > rollback/config/config.yaml << EOF
rollback:
  strategies:
    - name: "immediate"
      conditions:
        - "anomaly_score > 0.9"
        - "error_rate > 0.1"
    - name: "gradual"
      conditions:
        - "anomaly_score > 0.7"
        - "error_rate > 0.05"
  monitoring:
    prometheus_port: 8083
    health_port: 8083
EOF

# Configure Region Sync
cat > sync/config/config.yaml << EOF
sync:
  regions:
    - name: "us-east-1"
      endpoint: "http://region-sync:8084"
    - name: "eu-west-1"
      endpoint: "http://region-sync-eu:8084"
    - name: "ap-southeast-1"
      endpoint: "http://region-sync-ap:8084"
  sync_interval: 300
  health_check:
    endpoint: "/health"
    timeout: 10
  monitoring:
    prometheus_port: 8084
    health_port: 8084
EOF

# Start the pipeline
echo "🚀 Starting GPU CI/CD Pipeline..."
docker-compose down || true
docker-compose up -d --build --scale gpu-worker=$GPU_COUNT

# Wait for services to be healthy
echo "⏳ Waiting for services to become healthy..."
for i in {1..30}; do
    if docker-compose ps | grep -q "healthy"; then
        echo "✅ All services are healthy!"
        break
    fi
    sleep 10
done

# Verify deployment
echo "🔍 Verifying deployment..."
if curl -f http://localhost/jenkins/login > /dev/null 2>&1; then
    echo "✅ Jenkins is accessible at http://localhost/jenkins"
else
    echo "❌ Jenkins is not accessible"
    exit 1
fi

if curl -f http://localhost/morpheus/health > /dev/null 2>&1; then
    echo "✅ Morpheus is accessible at http://localhost/morpheus"
else
    echo "❌ Morpheus is not accessible"
    exit 1
fi

if curl -f http://localhost/canary/health > /dev/null 2>&1; then
    echo "✅ Canary Service is accessible at http://localhost/canary"
else
    echo "❌ Canary Service is not accessible"
    exit 1
fi

if curl -f http://localhost/rollback/health > /dev/null 2>&1; then
    echo "✅ Rollback Service is accessible at http://localhost/rollback"
else
    echo "❌ Rollback Service is not accessible"
    exit 1
fi

if curl -f http://localhost/sync/health > /dev/null 2>&1; then
    echo "✅ Region Sync Service is accessible at http://localhost/sync"
else
    echo "❌ Region Sync Service is not accessible"
    exit 1
fi

if curl -f http://localhost/metrics > /dev/null 2>&1; then
    echo "✅ Prometheus metrics are accessible at http://localhost/metrics"
else
    echo "❌ Prometheus metrics are not accessible"
    exit 1
fi

if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana is accessible at http://localhost:3000"
else
    echo "❌ Grafana is not accessible"
    exit 1
fi

echo ""
echo "🎉 GPU CI/CD Pipeline Successfully Deployed!"
echo ""
echo "Access Points:"
echo "  - Jenkins:        http://localhost/jenkins"
echo "  - Morpheus:       http://localhost/morpheus"
echo "  - Canary Service: http://localhost/canary"
echo "  - Rollback Service: http://localhost/rollback"
echo "  - Region Sync:    http://localhost/sync"
echo "  - Prometheus:     http://localhost/metrics"
echo "  - Grafana:        http://localhost:3000"
echo "  - Health Check:   http://localhost/health"
echo ""
echo "Next Steps:"
echo "  1. Configure Jenkins with your repository"
echo "  2. Set up GPU training data in ./data/"
echo "  3. Configure Morpheus anomaly detection rules"
echo "  4. Set up monitoring dashboards in Grafana"
echo ""
