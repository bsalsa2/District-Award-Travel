#!/bin/bash

# Start the Kubernetes cluster
docker-compose up -d

# Deploy the award travel platform
kubectl apply -f award-travel-platform.yaml

# Configure monitoring and logging
kubectl apply -f monitoring.yaml
kubectl apply -f logging.yaml
