# Feature: Kubernetes Migration

## Overview

Migrate the layering detection analytics microservices from AWS ECS to Kubernetes. This migration enables better portability, advanced orchestration features, and standardized container management while maintaining all existing functionality and infrastructure dependencies.

**Current Architecture**: AWS ECS Fargate with ALB, EFS storage, CloudWatch logging, Secrets Manager, and auto-scaling.

**Target Architecture**: AWS EKS (Kubernetes) with equivalent functionality using native K8s resources, maintaining integration with existing AWS services (EFS, Secrets Manager, CloudWatch).

## Requirements

### Phase 1: Core Kubernetes Resources
- [ ] Create `k8s/` directory structure
- [ ] Define namespace: `layering-detection` (or per-environment)
- [ ] Create service accounts with appropriate RBAC
- [ ] Extract environment variables from Terraform ECS config
- [ ] Create ConfigMaps for service URLs and application config
- [ ] Create Secrets using External Secrets Operator (syncs from AWS Secrets Manager)
- [ ] Store `API_KEY` and `PSEUDONYMIZATION_SALT` securely

### Phase 2: Storage Migration
- [ ] Set up Persistent Volumes using EFS CSI Driver (AWS EKS)
- [ ] Create StorageClass: `efs-sc` (for EFS) or equivalent
- [ ] Create PersistentVolumeClaims: `input-pvc`, `output-pvc`, `logs-pvc`
- [ ] Mount `input-pvc` at `/app/input` (read-only) for orchestrator
- [ ] Mount `output-pvc` at `/app/output` and `logs-pvc` at `/app/logs` (read-write) for aggregator
- [ ] Verify volume access permissions

### Phase 3: Deployments & Services
- [ ] Convert ECS task definitions to K8s Deployments
- [ ] Map resource requests/limits from Terraform variables
- [ ] Convert ECS health checks to liveness/readiness probes
- [ ] Set initial replica counts from `desired_count` variable
- [ ] Create ClusterIP services for internal communication
- [ ] Update orchestrator env vars to use K8s service names (DNS auto-resolves)
- [ ] Replace ALB with Ingress resource
- [ ] Configure AWS Load Balancer Controller for Ingress (creates ALBs automatically)
- [ ] Set up TLS termination if HTTPS required

### Phase 4: Auto-Scaling
- [ ] Replace ECS auto-scaling with HorizontalPodAutoscaler (HPA)
- [ ] Configure CPU-based scaling (target: 70% utilization)
- [ ] Configure memory-based scaling (target: 80% utilization)
- [ ] Set min/max replicas from Terraform variables
- [ ] Configure scale-in/scale-out cooldown periods
- [ ] Optionally implement Vertical Pod Autoscaler (VPA) for right-sizing

### Phase 5: Monitoring & Logging
- [ ] Set up logging via Fluent Bit to CloudWatch (IRSA integration)
- [ ] Configure metrics collection using CloudWatch Container Insights
- [ ] Export same metrics as CloudWatch alarms
- [ ] Set up observability (optional service mesh, distributed tracing)

### Phase 6: CI/CD Updates
- [ ] Update GitHub Actions workflow for K8s deployment
- [ ] Add K8s deployment job (after image build)
- [ ] Use `kubectl` or Helm for deployment
- [ ] Configure environment-specific configs (dev/staging/prod)
- [ ] Ensure K8s cluster has ECR pull permissions (IRSA for service accounts)

## Acceptance Criteria

### Phase 1: Core Resources
- [ ] All services deploy successfully to Kubernetes cluster
- [ ] ConfigMaps contain all required environment variables
- [ ] Secrets are accessible to pods via External Secrets Operator (synced from AWS Secrets Manager)
- [ ] Service accounts have appropriate RBAC permissions
- [ ] Namespace isolation works correctly

### Phase 2: Storage
- [ ] All PVCs are bound and accessible
- [ ] Orchestrator can read from `input-pvc` at `/app/input`
- [ ] Aggregator can write to `output-pvc` at `/app/output`
- [ ] Aggregator can write to `logs-pvc` at `/app/logs`
- [ ] File permissions are correct (read-only for input, read-write for output/logs)
- [ ] Data persists across pod restarts

### Phase 3: Deployments & Services
- [ ] All 4 services (orchestrator, layering, wash-trading, aggregator) are deployed
- [ ] Resource requests/limits match ECS configuration
- [ ] Health checks (liveness/readiness probes) pass
- [ ] Services can communicate via K8s DNS names
- [ ] Ingress routes traffic correctly to services
- [ ] External access works (via Ingress)
- [ ] TLS termination works (if configured)

### Phase 4: Auto-Scaling
- [ ] HPA scales pods based on CPU utilization (target: 70%)
- [ ] HPA scales pods based on memory utilization (target: 80%)
- [ ] Min/max replica limits are enforced
- [ ] Scaling cooldown periods work correctly
- [ ] Metrics server is installed and working

### Phase 5: Monitoring & Logging
- [ ] Logs are collected and viewable (CloudWatch or native)
- [ ] Metrics are exported (CloudWatch or Prometheus)
- [ ] Alarms/alerts match ECS CloudWatch alarms
- [ ] Dashboard shows service metrics

### Phase 6: CI/CD
- [ ] GitHub Actions builds and pushes images to registry
- [ ] GitHub Actions deploys to K8s cluster
- [ ] Environment-specific configs work (dev/staging/prod)
- [ ] Rollback mechanism works

### Overall
- [ ] All ECS functionality is replicated in K8s
- [ ] Zero-downtime migration strategy is documented
- [ ] Rollback plan is documented and tested
- [ ] End-to-end tests pass against K8s deployment
- [ ] Performance matches or exceeds ECS deployment
- [ ] Documentation updated with K8s deployment instructions

## Technical Details

### Service Discovery Changes

**Current (Docker Compose/ECS)**:
- `http://layering-service:8001`
- `http://wash-trading-service:8002`
- `http://aggregator-service:8003`

**Kubernetes**:
- Same DNS names work via K8s Service DNS
- Format: `http://<service-name>.<namespace>.svc.cluster.local:<port>`
- Short form: `http://<service-name>:<port>` (same namespace)

No code changes needed if services are in same namespace.

### Configuration Mappings

| ECS Component | Kubernetes Equivalent |
|---------------|----------------------|
| Task Definition | Deployment + ConfigMap + Secrets |
| ECS Service | Deployment + Service |
| ALB Target Group | Service + Ingress |
| EFS Volume | PersistentVolumeClaim (EFS CSI) |
| ECS Auto-Scaling | HorizontalPodAutoscaler |
| CloudWatch Logs | Fluent Bit → CloudWatch (IRSA) |
| Secrets Manager | External Secrets Operator (syncs from AWS Secrets Manager) |
| Security Groups | Network Policies (optional) |

### Resource Requirements

**From Terraform variables** (`terraform/variables.tf`):

**CPU (1024 = 1 vCPU)**:
- Orchestrator: 512 (0.5 vCPU)
- Layering: 512 (0.5 vCPU)
- Wash Trading: 512 (0.5 vCPU)
- Aggregator: 512 (0.5 vCPU)

**Memory (MB)**:
- Orchestrator: 1024 MB
- Layering: 512 MB
- Wash Trading: 512 MB
- Aggregator: 512 MB

**Replica Counts**:
- Orchestrator: 1 (min: 1, max: 5)
- Layering: 2 (min: 1, max: 10)
- Wash Trading: 2 (min: 1, max: 10)
- Aggregator: 1 (min: 1, max: 5)

### Environment Variables

**Orchestrator** (from `terraform/ecs.tf` lines 43-53):
- `PORT=8000`
- `INPUT_DIR=/app/input`
- `LAYERING_SERVICE_URL=http://layering-service:8001`
- `WASH_TRADING_SERVICE_URL=http://wash-trading-service:8002`
- `AGGREGATOR_SERVICE_URL=http://aggregator-service:8003`
- `MAX_RETRIES=3`
- `ALGORITHM_TIMEOUT_SECONDS=30`
- `LOG_LEVEL=INFO`
- `RATE_LIMIT_PER_MINUTE=100`
- `API_KEY` (from Secrets)

**Layering Service**:
- `PORT=8001`
- `LOG_LEVEL=INFO`
- `RATE_LIMIT_PER_MINUTE=100`
- `API_KEY` (from Secrets)

**Wash Trading Service**:
- `PORT=8002`
- `LOG_LEVEL=INFO`
- `RATE_LIMIT_PER_MINUTE=100`
- `API_KEY` (from Secrets)

**Aggregator Service**:
- `PORT=8003`
- `OUTPUT_DIR=/app/output`
- `LOGS_DIR=/app/logs`
- `VALIDATION_STRICT=true`
- `ALLOW_PARTIAL_RESULTS=false`
- `LOG_LEVEL=INFO`
- `RATE_LIMIT_PER_MINUTE=100`
- `API_KEY` (from Secrets)
- `PSEUDONYMIZATION_SALT` (from Secrets)

### Health Checks

**ECS Health Check** (from `terraform/ecs.tf` lines 183-189):
```bash
python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health', timeout=5).read()" || exit 1
```
- Interval: 30s
- Timeout: 10s
- Start Period: 5s
- Retries: 3

**Kubernetes Equivalent**:
- Liveness probe: HTTP GET `/health` (interval: 30s, timeout: 10s, initialDelaySeconds: 5, failureThreshold: 3)
- Readiness probe: HTTP GET `/health` (interval: 10s, timeout: 5s, failureThreshold: 3)

### Auto-Scaling Configuration

**ECS Auto-Scaling** (from `terraform/autoscaling.tf`):
- CPU target: 70%
- Memory target: 80%
- Scale-in cooldown: 300s
- Scale-out cooldown: 60s

**Kubernetes HPA**:
- CPU target: 70%
- Memory target: 80%
- Scale-down stabilization: 5 minutes
- Scale-up stabilization: 1 minute

### File Structure

```
k8s/
├── base/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── external-secrets.yaml
│   └── storage/
│       ├── storageclass.yaml (EFS CSI)
│       ├── input-pvc.yaml
│       ├── output-pvc.yaml
│       └── logs-pvc.yaml
├── services/
│   ├── orchestrator/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── hpa.yaml
│   ├── layering/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── hpa.yaml
│   ├── wash-trading/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── hpa.yaml
│   └── aggregator/
│       ├── deployment.yaml
│       ├── service.yaml
│       └── hpa.yaml
├── ingress/
│   └── ingress.yaml
├── monitoring/
│   ├── fluent-bit.yaml
│   └── cloudwatch-dashboard.yaml
└── overlays/
    ├── dev/
    ├── staging/
    └── prod/
```

## Implementation Notes

### Zero-Downtime Migration Strategy

1. **Dual Deployment**: Deploy K8s resources alongside ECS (optional dual-write)
2. **Testing**: Test K8s deployment thoroughly in dev/staging
3. **Cutover**: Update DNS/Ingress to point to K8s
4. **Monitoring**: Monitor both systems during transition
5. **Decommission**: Decommission ECS after validation

### Rollback Plan

- Keep ECS infrastructure until K8s is stable
- Terraform state allows quick ECS restoration
- Version control all K8s manifests
- Document rollback procedure

### Testing Strategy

- Use `kubectl port-forward` for local testing
- Deploy to dev namespace first
- Run E2E tests against K8s deployment
- Validate storage, networking, scaling
- Performance testing to ensure parity with ECS

### Dependencies & Prerequisites

**Kubernetes Cluster**:
- **AWS EKS** (Kubernetes 1.24+)
- AWS Load Balancer Controller installed
- EFS CSI driver installed
- Metrics server installed (for HPA)
- External Secrets Operator installed
- Fluent Bit DaemonSet (for CloudWatch logging)

**AWS Prerequisites**:
- EKS cluster with IRSA (IAM Roles for Service Accounts) enabled
- IAM roles for service accounts (ECR access, CloudWatch logging, Secrets Manager)
- Existing EFS file system (reuse from ECS)
- Existing Secrets Manager secrets (API_KEY, PSEUDONYMIZATION_SALT)

**Tools**:
- `kubectl` configured with EKS cluster access
- `kustomize` (for environment overlays)
- `helm` (optional, for External Secrets Operator installation)

## Decisions & Recommendations

### Platform & Infrastructure

- **K8s Platform**: **AWS EKS** - Seamless integration with existing AWS services (EFS, Secrets Manager, CloudWatch), IRSA support, native EFS CSI driver
- **Image Registry**: **ECR** - Already configured, better EKS integration, minimal CI/CD changes
- **Multi-Environment**: **Separate namespaces** (dev/staging/prod) - Single cluster, lower cost, easier management, Kustomize overlays

### Networking & Access

- **Ingress Controller**: **AWS Load Balancer Controller** - Native AWS integration, creates ALBs automatically, CloudWatch metrics, IRSA support
- **TLS**: **Yes for production** - Use cert-manager with AWS Certificate Manager (ACM) for automatic certificate management via IRSA

### Security & Secrets

- **Secrets Management**: **External Secrets Operator** - Syncs from existing AWS Secrets Manager, no duplication, better security, matches current architecture
- **Network Policies**: **Not initially** - Add later for security hardening after core migration is stable
- **Service Mesh**: **Not needed initially** - Adds complexity without clear benefit for this use case

### Observability

- **Logging**: **CloudWatch via Fluent Bit** - Reuses existing CloudWatch Logs, IRSA integration, familiar tooling, no new infrastructure
- **Metrics**: **CloudWatch Container Insights** - Native EKS integration, reuses existing CloudWatch dashboards, no additional infrastructure

### Implementation Strategy

1. **Start with dev namespace** - Test thoroughly before production
2. **Keep ECS running** - Dual deployment during migration, easy rollback
3. **Reuse existing infrastructure** - EFS file system, Secrets Manager secrets, CloudWatch dashboards
4. **IRSA for all AWS access** - No long-lived credentials, secure by default

### Cost Considerations

- **EKS Control Plane**: ~$0.10/hour (~$73/month)
- **ALB**: ~$0.0225/hour per ALB (~$16/month)
- **EFS**: Pay per use (reuse existing)
- **CloudWatch**: Pay per use (same as ECS)
- **Estimated additional cost**: ~$100-150/month for EKS + ALB vs ECS Fargate

## Related Specs

- [Docker Infrastructure](./FEATURE-docker-infrastructure.md)
- [Service Health Checks](./FEATURE-service-health-checks.md)
- [Logging & Observability](./FEATURE-logging-observability.md)
- [Microservices Architecture](./ARCHITECTURE-MICROSERVICES.md)
- [Migration Path](./FEATURE-migration-path.md)

## References

- Terraform ECS Configuration: `terraform/ecs.tf`
- Terraform Variables: `terraform/variables.tf`
- Terraform Auto-Scaling: `terraform/autoscaling.tf`
- Terraform Monitoring: `terraform/monitoring.tf`
- Terraform ALB: `terraform/alb.tf`
- CI/CD Workflow: `.github/workflows/ci.yml`
