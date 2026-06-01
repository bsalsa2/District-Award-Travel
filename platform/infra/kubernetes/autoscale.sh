#!/bin/bash

# Set the autoscaling configuration for the dashboard deployment
kubectl autoscale deployment kubernetes-dashboard --min=1 --max=5 --cpu-percent=50

# Set the autoscaling configuration for the metrics-server deployment
kubectl autoscale deployment metrics-server --min=1 --max=5 --cpu-percent=50
