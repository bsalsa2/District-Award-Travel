#!/bin/bash

# Monitor Kubernetes cluster
kubectl get nodes -o wide
kubectl get pods -o wide
kubectl get deployments -o wide
kubectl get services -o wide

# Monitor Docker containers
docker ps -a
docker logs -f kubernetes-master
docker logs -f kubernetes-etcd
docker logs -f kubernetes-worker
docker logs -f nginx
