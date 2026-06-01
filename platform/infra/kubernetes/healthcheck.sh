#!/bin/bash

# Check if the Kubernetes cluster is running
if ! kind get clusters | grep -q district-award-travel; then
    echo "Kubernetes cluster is not running"
    exit 1
fi

# Check if the dashboard is running
if ! kubectl get deployments -n kube-system | grep -q kubernetes-dashboard; then
    echo "Kubernetes dashboard is not running"
    exit 1
fi

# Check if the metrics-server is running
if ! kubectl get deployments -n kube-system | grep -q metrics-server; then
    echo "Metrics-server is not running"
    exit 1
fi
