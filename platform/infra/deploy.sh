#!/bin/bash

# Start Docker Compose
docker-compose up -d

# Initialize Kubernetes cluster
kubeadm init --pod-network-cidr 10.244.0.0/16

# Join worker nodes to the cluster
kubeadm join 127.0.0.1:6443

# Apply deployment and service configurations
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml

# Verify deployment and service status
kubectl get deployments
kubectl get services
