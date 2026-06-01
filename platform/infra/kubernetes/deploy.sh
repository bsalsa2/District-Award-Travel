#!/bin/bash

# Create a Kubernetes cluster
kind create cluster --name district-award-travel

# Apply the dashboard deployment
kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.5.0/aio/deploy/recommended.yaml

# Apply the metrics-server deployment
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Expose the dashboard service
kubectl expose deployment kubernetes-dashboard --type=NodePort --port=80

# Create a service account for the dashboard
kubectl create serviceaccount dashboard-admin -n default

# Bind the service account to the cluster-admin role
kubectl create clusterrolebinding dashboard-admin --clusterrole=cluster-admin --serviceaccount=default:dashboard-admin
