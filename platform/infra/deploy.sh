#!/bin/bash

# Create namespace
kubectl create namespace award-travel-ns

# Apply deployment configuration
kubectl apply -f deployment.yaml -n award-travel-ns

# Apply service configuration
kubectl apply -f service.yaml -n award-travel-ns

# Apply ingress configuration
kubectl apply -f ingress.yaml -n award-travel-ns
