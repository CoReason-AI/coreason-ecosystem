#!/bin/bash
# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

set -e

echo "Deploying Chaos Mesh into local orchestration matrix..."

# Add Chaos Mesh Helm repo
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update

# Install Chaos Mesh
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
    --namespace=chaos-mesh \
    --create-namespace \
    --set chaosDaemon.runtime=containerd \
    --set chaosDaemon.socketPath=/run/containerd/containerd.sock \
    --version 2.7.0

echo "Applying strict RoleBinding boundaries for urn:coreason:actionspace:effector:chaos_mesh:v1..."
kubectl apply -f chaos-mesh-rbac.yaml

echo "Chaos Mesh boundary provisioned successfully."
