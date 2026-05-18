# CoReason Enterprise Platform — Installation Guide

*Copyright (c) 2026 CoReason, Inc. Licensed under the Prosperity Public License 3.0.*

---

## Overview

This guide walks you through deploying the CoReason Enterprise Platform onto your Kubernetes cluster using a single bootstrap manifest. The bootstrap configures OCI registry credentials and deploys the full CoReason stack via ArgoCD GitOps.

**What gets deployed:**

| Component | Helm Chart | Version | Description |
|---|---|---|---|
| **CoReason Core** | `coreason-enterprise` | Independent | Gateway, Runtime, Temporal, Neo4j, Milvus, Dex |
| **CoReason Mesh** | `coreason-mesh` | Independent | Governance Plane, Istio mesh config, LanceDB |
| **Observability** | `coreason-observability` | Independent | Prometheus, Grafana, OTel Collector (toggleable) |

> **Note:** Each chart maintains independent semantic versioning. The ArgoCD App-of-Apps repository acts as the bill of materials, locking specific chart versions into a tested release topology.

---

## Prerequisites

| Requirement | Minimum Version | Notes |
|---|---|---|
| Kubernetes cluster | v1.28+ | EKS, GKE, AKS, or bare-metal |
| `kubectl` | v1.28+ | Configured with cluster-admin privileges |
| Helm | v3.15+ | Required for manual chart operations |
| StorageClass | — | A default `StorageClass` must be configured |
| CoReason OCI Token | — | Provided by CoReason sales (`license@coreason.ai`) |

### Network Requirements (Tier 1 Only)

| Destination | Port | Purpose |
|---|---|---|
| `ghcr.io` | 443 | Pull CoReason OCI artifacts (Docker images + Helm charts) |
| `github.com` | 443 | ArgoCD Git sync for App-of-Apps manifests |

---

## Distribution Tiers

CoReason supports two distribution models based on your network classification:

### Tier 1: Connected VPC / Hyperscaler (GHCR PAT Model)

For standard enterprise deployments with outbound internet access. CoReason mints a unique GitHub Personal Access Token (PAT) scoped to `read:packages`. You inject this as an `imagePullSecret` in your cluster. If your contract expires, the PAT is revoked.

### Tier 2: Air-Gapped / High-Compliance (Replicated Model)

For intelligence agencies, financial mainframes, or sovereign enclaves with zero internet access. CoReason packages the same OCI artifacts into a `.airgap` tarball delivered via Replicated. Replicated handles node-locked licensing, cryptographic entitlement checks, and local registry mirroring.

> **Tier 2 clients:** Contact `license@coreason.ai` for air-gapped deployment instructions. The remainder of this guide covers Tier 1 (connected) deployments.

---

## Step 1: Choose Your Bootstrap Path

CoReason provides two bootstrap manifests:

| File | Use When |
|---|---|
| `bootstrap-app.yaml` | Your cluster **already has ArgoCD** installed |
| `bootstrap-full.yaml` | Your cluster **does not have ArgoCD** |

### Path A: Existing ArgoCD (Recommended)

If your cluster already runs ArgoCD:

```bash
# Download the lightweight bootstrap
curl -sLO https://raw.githubusercontent.com/CoReason-AI/coreason-ecosystem/main/isv-distribution/bootstrap/bootstrap-app.yaml
```

### Path B: No ArgoCD (Full Bootstrap)

If your cluster does not have ArgoCD:

```bash
# Step 1: Install ArgoCD (pinned to v2.14.x stable)
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.14.11/manifests/install.yaml

# Step 2: Wait for ArgoCD to become ready
kubectl wait --for=condition=Available deployment/argocd-server -n argocd --timeout=300s

# Step 3: Download the full bootstrap
curl -sLO https://raw.githubusercontent.com/CoReason-AI/coreason-ecosystem/main/isv-distribution/bootstrap/bootstrap-full.yaml
```

---


## Step 2: Configure Credentials

CoReason provides two credential management paths. Choose the one that fits your organization's security posture.

### Path A: External Secrets Operator (Recommended for Enterprise)

The External Secrets Operator (ESO) automatically syncs credentials from your existing secret backend (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager, or Azure Key Vault) into Kubernetes. **ESO is included in the CoReason ApplicationSet** and deploys automatically as sync-wave 0.

**Before bootstrapping, store your CoReason OCI credentials in your secret backend:**

| Key Path | Property | Value |
|---|---|---|
| `coreason/oci-credentials` | `username` | Your GitHub username or robot account |
| `coreason/oci-credentials` | `password` | Your CoReason OCI token (scoped to `read:packages`) |
| `coreason/oci-credentials` | `email` | Contact email for registry account |

**Then configure the ClusterSecretStore:**

```bash
# Download and configure the ClusterSecretStore template
curl -sLO https://raw.githubusercontent.com/CoReason-AI/coreason-ecosystem/main/isv-distribution/external-secrets/cluster-secret-store.yaml

# Edit cluster-secret-store.yaml:
#   1. Uncomment the provider block for your backend (AWS/Vault/GCP/Azure)
#   2. Fill in your environment-specific values (region, vault URL, project ID, etc.)
#   3. Remove the 'fake' provider placeholder

# Apply the ExternalSecret CRs that create the image pull + ArgoCD secrets
curl -sLO https://raw.githubusercontent.com/CoReason-AI/coreason-ecosystem/main/isv-distribution/external-secrets/external-secrets.yaml
```

> **Note:** The `external-secrets.yaml` file creates two Kubernetes Secrets automatically via ESO:
> - `coreason-registry-credentials` in `coreason-system` — Docker image pull secret
> - `coreason-oci-helm-creds` in `argocd` — ArgoCD OCI Helm chart pull secret
>
> Both secrets refresh every 1 hour. ESO handles rotation automatically when you rotate credentials in your backend.

### Path B: Manual kubectl (Lightweight / Dev Clusters)

If you don't use an external secret backend, create the secrets manually:

```bash
# 1. Create the namespace
kubectl create namespace coreason-system --dry-run=client -o yaml | kubectl apply -f -

# 2. Create the image pull secret for workload pods
kubectl create secret docker-registry coreason-registry-credentials \
  --namespace=coreason-system \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_COREASON_OCI_TOKEN \
  --docker-email=YOUR_EMAIL

# 3. Create ArgoCD OCI registry credentials (for Helm chart pulls)
kubectl create secret generic coreason-oci-helm-creds \
  --namespace=argocd \
  --from-literal=type=helm \
  --from-literal=name=coreason-charts \
  --from-literal=url=ghcr.io/coreason-ai/charts \
  --from-literal=enableOCI=true \
  --from-literal=username=YOUR_GITHUB_USERNAME \
  --from-literal=password=YOUR_COREASON_OCI_TOKEN

# 4. Label the secret so ArgoCD discovers it as a repository
kubectl label secret coreason-oci-helm-creds -n argocd \
  argocd.argoproj.io/secret-type=repository
```

> **Security Note:** Credentials are created exclusively via `kubectl` — they are never embedded in YAML files. If using Path B, you are responsible for credential rotation.

> Replace `YOUR_GITHUB_USERNAME`, `YOUR_COREASON_OCI_TOKEN`, and `YOUR_EMAIL` with the credentials provided by CoReason. Contact `license@coreason.ai` if you haven't received your token.

---

## Step 3: Deploy the Platform

Apply the bootstrap manifest (no editing required):

```bash
# For clusters WITH existing ArgoCD:
kubectl apply -f bootstrap-app.yaml

# For clusters WITHOUT ArgoCD:
kubectl apply -f bootstrap-full.yaml
```

If using **Path A** (External Secrets), also apply:

```bash
kubectl apply -f cluster-secret-store.yaml
kubectl apply -f external-secrets.yaml
```

Apply the ArgoCD custom health checks (required for sync-wave gating):

```bash
# Teaches ArgoCD to understand ESO CRD health status.
# Without this, ExternalSecrets stay "Progressing" forever and block wave 1.
kubectl apply -f gitops/argocd-cm-health-checks.yaml
```

This will:
1. Create the `coreason-system` and `external-secrets` namespaces
2. Create the `coreason` AppProject with strict RBAC boundaries
3. Deploy the root ArgoCD Application, which discovers the CoReason `ApplicationSet`
4. The ApplicationSet automatically generates and manages all child applications:
   - `coreason-external-secrets` (sync-wave 0) — External Secrets Operator
   - `coreason-core` (sync-wave 1) — Gateway, Runtime, infrastructure
   - `coreason-mesh` (sync-wave 2) — Governance Plane, MCP Router
   - `coreason-observability` (sync-wave 3) — Prometheus, Grafana, OTel

### Sync-Wave Health Gating

ArgoCD will **not** proceed from wave N to wave N+1 until all resources in wave N are **Healthy**:

| Wave | Readiness Gate | What Blocks Progress |
|---|---|---|
| 0 (ESO) | ESO pods pass readiness probe, ExternalSecrets report `Ready: True` | Backend auth failure, missing secret path |
| 1 (Core) | Gateway + Runtime pods pass startup → readiness probes | Image pull failure, `/healthz` endpoint down |
| 2 (Mesh) | Mesh pods pass startup → readiness probes | MCP router initialization failure |
| 3 (Observability) | Prometheus/Grafana/OTel pods report Ready | Storage provisioning, PVC binding |


---

## Step 4: Monitor Deployment Health

### ArgoCD UI

```bash
# Port-forward the ArgoCD server
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Get the initial admin password
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 -d
```

Navigate to `https://localhost:8080` and log in with **admin** / (password from above).

You should see three applications syncing:
- `coreason-core` — Enterprise stack
- `coreason-mesh` — Governance Plane
- `coreason-observability` — Monitoring stack

### Grafana Dashboards

```bash
kubectl port-forward svc/coreason-observability-grafana -n coreason-system 3000:80
```

Navigate to `http://localhost:3000` — log in with **admin** / `coreason-admin`.

### Health Check Commands

```bash
# Verify all pods are running
kubectl get pods -n coreason-system

# Check ArgoCD application sync status
kubectl get applications -n argocd

# Verify CoReason runtime is healthy
kubectl logs -n coreason-system -l app=coreason-runtime --tail=50
```

---

## Step 5: Disable Observability (Optional)

If your organization has a mandated monitoring stack (Datadog, Dynatrace, etc.), disable the CoReason observability chart:

```bash
# Option 1: Patch the ArgoCD Application
kubectl patch application coreason-observability -n argocd --type merge \
  -p '{"spec":{"source":{"helm":{"values":"enabled: false\nprometheus:\n  enabled: false\notelCollector:\n  enabled: false"}}}}'

# Option 2: Delete the observability application entirely
kubectl delete application coreason-observability -n argocd
```

---

## Upgrade Strategy

Each CoReason Helm chart maintains **independent semantic versioning**. The ArgoCD `targetRevision` controls update behavior:

| Update Type | Behavior | Example |
|---|---|---|
| **Patch** (x.y.Z) | Automatic — ArgoCD syncs immediately | `0.1.0` → `0.1.1` |
| **Minor** (x.Y.0) | Manual — update `targetRevision` | `0.1.0` → `0.2.0` |
| **Major** (X.0.0) | Manual — requires CoReason upgrade runbook | `0.x.x` → `1.0.0` |

### Manual Upgrade

```bash
# Update the core chart to accept the next minor
kubectl patch application coreason-core -n argocd --type merge \
  -p '{"spec":{"source":{"targetRevision":"~0.2.0"}}}'

# Update the mesh chart independently
kubectl patch application coreason-mesh -n argocd --type merge \
  -p '{"spec":{"source":{"targetRevision":"~0.2.0"}}}'
```

### Rollback

```bash
# List sync history
argocd app history coreason-core

# Rollback to a specific revision
argocd app rollback coreason-core <REVISION_NUMBER>
```

---

## Troubleshooting

| Symptom | Cause | Resolution |
|---|---|---|
| `ImagePullBackOff` on pods | Invalid or expired OCI token | Recreate `coreason-registry-credentials` secret with a valid PAT |
| ArgoCD `ComparisonError` | OCI registry unreachable | Verify outbound to `ghcr.io:443` |
| `SyncFailed` on observability | Missing `StorageClass` | Ensure a default SC exists: `kubectl get sc` |
| Temporal `CrashLoopBackOff` | PostgreSQL not ready | Check: `kubectl logs -n coreason-system -l app=postgres` |
| HPA not scaling | Metrics server missing | `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml` |

### Diagnostics

```bash
kubectl get all -n coreason-system -o wide
kubectl describe application coreason-core -n argocd
kubectl get events -n coreason-system --sort-by='.lastTimestamp'
```

---

## Uninstallation

```bash
# Delete root application (cascading delete of all children)
kubectl delete application coreason-platform -n argocd

# Wait for ArgoCD to prune all resources
sleep 30

# Remove namespaces
kubectl delete namespace coreason-system

# Remove cluster-scoped RBAC (if using bootstrap-full)
kubectl delete clusterrole coreason-argocd-controller
kubectl delete clusterrolebinding coreason-argocd-controller-binding
```

---

## Supply Chain Security

All CoReason OCI artifacts are cryptographically signed using [Sigstore Cosign](https://docs.sigstore.dev/).

### Verify Artifacts

```bash
# Verify a Helm chart
cosign verify ghcr.io/coreason-ai/charts/coreason-enterprise:0.1.0

# Verify a Docker image
cosign verify ghcr.io/coreason-ai/coreason-ecosystem:latest
```

### Kubernetes Policy Enforcement (Kyverno)

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-coreason-images
spec:
  validationFailureAction: Enforce
  rules:
    - name: verify-signature
      match:
        any:
          - resources:
              kinds:
                - Pod
      verifyImages:
        - imageReferences:
            - "ghcr.io/coreason-ai/*"
          attestors:
            - entries:
                - keyless:
                    url: https://fulcio.sigstore.dev
                    rekor:
                      url: https://rekor.sigstore.dev
```

---

## Support

| Channel | Contact |
|---|---|
| Enterprise Support | `support@coreason.ai` |
| Licensing & Tokens | `license@coreason.ai` |
| Air-Gap Deployments | `license@coreason.ai` (Replicated Tier 2) |

*Copyright (c) 2026 CoReason, Inc. Licensed under the Prosperity Public License 3.0.*
