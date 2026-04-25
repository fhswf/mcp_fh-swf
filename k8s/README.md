# Kubernetes Deployment Structure

## Übersicht

Die K8S-Konfiguration wurde auf Kustomize overlays umgestellt mit separaten Umgebungen für **Staging** (main branch) und **Prod** (prod branch).

### Struktur

```
k8s/
├── base/                    # Base Konfiguration (gemeinsam für alle Umgebungen)
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── ingress.yaml
│   ├── pvc.yaml
│   └── neo4j.yaml
└── overlays/
    ├── staging/            # main branch → mcp-fh-swf-staging namespace
    │   ├── kustomization.yaml
    │   ├── deployment-patch.yaml
    │   └── ingress-patch.yaml
    └── prod/               # prod branch → mcp-fh-swf-prod namespace
        ├── kustomization.yaml
        ├── deployment-patch.yaml
        └── ingress-patch.yaml
```

## Umgebungen

### Staging (main branch)
- **Namespace:** `mcp-fh-swf-staging`
- **Domain:** `mcp-staging.fh-swf.cloud`
- **Replicas:** 1
- **Log Level:** INFO
- **Autoupdate:** Jeder Push zu main

### Production (prod branch)
- **Namespace:** `mcp-fh-swf-prod`
- **Domain:** `mcp.fh-swf.cloud`
- **Replicas:** 2 (mit Pod Anti-Affinity)
- **Log Level:** WARNING
- **Resource Limits:** CPU 500m, Memory 1Gi
- **Autoupdate:** Nur bei Release-Tags

## CI/CD Pipeline & Image Tags

### Image Tag Strategy für ArgoCD

Statt `latest` werden konkrete Tags verwendet, damit ArgoCD Änderungen erkennt:

| Environment | Tag Format | Example | Trigger |
|-------------|-----------|---------|---------|
| **Staging** | `main-{short-sha}` | `main-a1b2c3d` | Jeder Push zu `main` |
| **Prod** | `{release-version}` | `v1.2.3` | Release-Tag erstellen |

### 1. Build Staging Image (main branch)
```mermaid
Push to main → Build Docker image with tag main-{short-sha}
                → Push to ghcr.io/$repo:main-{short-sha}
                → Deploy to Staging via Deploy Workflow
```

**Workflow:** `.github/workflows/build-staging.yaml`
- Triggered bei jedem Push zu main
- Baut Docker Image mit Git SHA Tag (z.B. `main-a1b2c3d`)
- Pusht zu GitHub Container Registry
- Cache-Layer für schnellere Builds

### 2. Release-Please (main branch)
```mermaid
main branch → release-please checks commits → Creates Release PR
                                              → On merge: Creates tag & Release
                                              → Builds Docker Image with Release Tag
                                              → Pushes to prod branch
```

**Workflow:** `.github/workflows/release-please.yaml`
- Überwacht `main` branch
- Erstellt automatische Release PRs basierend auf Conventional Commits
- Beim Merge:
  - Tag + Release erstellen (z.B. `v1.2.3`)
  - Docker Image bauen mit Release Tag
  - Automatisch zu `prod` branch pushen

### 3. Deploy Workflow
```mermaid
Push to main → Deploy to Staging with image tag main-{sha}
Push to prod → Deploy to Production with image tag v{version}
```

**Workflow:** `.github/workflows/deploy.yaml`
- Triggered bei Push zu main oder prod
- Bestimmt Image Tag basierend auf Branch:
  - **Staging (main):** `main-{short-sha}` (von Git commit)
  - **Prod (prod):** `{release-tag}` (von Git tags)
- Ersetzt Placeholder in Kustomize Overlays
- Deployt zu Kubernetes

## Verwendung

### Lokal Kustomize aufbauen
```bash
# Staging manifests
kustomize build k8s/overlays/staging > staging-manifests.yaml

# Prod manifests
kustomize build k8s/overlays/prod > prod-manifests.yaml
```

### Manually deployen
```bash
kubectl apply -k k8s/overlays/staging
kubectl apply -k k8s/overlays/prod
```

### Status überprüfen
```bash
kubectl get deployments,services,ingress -n mcp-fh-swf-staging
kubectl get deployments,services,ingress -n mcp-fh-swf-prod
```

## Branch-Strategie

- **main:** Entwicklung, Staging Deployment
- **prod:** Produktive Releases

## Commits & Releases

Die Release-Version wird automatisch aus Conventional Commits bestimmt:

```
feat: ...         → Minor version bump
fix: ...          → Patch version bump
feat!: ...        → Major version bump
```

Beispiel:
```
feat: Add new API endpoint
→ Creates PR: "chore: release 1.2.0"
→ On merge: Tag v1.2.0, Release erstellt, zu prod gepusht
```
