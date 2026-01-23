# Kubernetes Migration Tasks

## Overview

This document breaks down the Kubernetes migration into atomic, implementable tasks ordered by dependencies. Each task is designed to be completable in 1-4 hours with clear acceptance criteria.

## Key Decisions

**Platform**: AWS EKS (Kubernetes 1.24+)  
**Image Registry**: ECR (existing)  
**Secrets**: External Secrets Operator (syncs from AWS Secrets Manager)  
**Storage**: EFS CSI Driver (reuse existing EFS file system)  
**Ingress**: AWS Load Balancer Controller (creates ALBs automatically)  
**Logging**: Fluent Bit → CloudWatch Logs (IRSA)  
**Metrics**: CloudWatch Container Insights  
**Environments**: Separate namespaces (dev/staging/prod) in single cluster  
**TLS**: cert-manager + AWS Certificate Manager (production)  
**Network Policies**: Not initially (add later)  
**Service Mesh**: Not needed

## Task Status Legend

- ⏳ **Pending**: Not started
- 🚧 **In Progress**: Currently being worked on
- ✅ **Complete**: Finished and verified
- ❌ **Blocked**: Cannot proceed due to dependency

## Implementation Phases

### Phase 1: Core Kubernetes Resources
**Goal**: Set up namespace, ConfigMaps, Secrets, and base infrastructure.

### Phase 2: Storage Migration
**Goal**: Migrate EFS volumes to Kubernetes PersistentVolumes.

### Phase 3: Deployments & Services
**Goal**: Convert ECS services to Kubernetes Deployments and Services.

### Phase 4: Auto-Scaling
**Goal**: Replace ECS auto-scaling with Kubernetes HPA.

### Phase 5: Monitoring & Logging
**Goal**: Set up logging and metrics collection in Kubernetes.

### Phase 6: CI/CD Updates
**Goal**: Update CI/CD pipeline for Kubernetes deployment.

---

## Phase 1: Core Kubernetes Resources

### Task 1.1: Create Kubernetes Directory Structure
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~0.5h  
**Dependencies**: None  
**Status**: ⏳ Pending

**Description**:
Create the `k8s/` directory structure following the planned organization.

**Acceptance Criteria**:
- [ ] Create `k8s/base/` directory
- [ ] Create `k8s/services/` directory with subdirectories for each service
- [ ] Create `k8s/ingress/` directory
- [ ] Create `k8s/monitoring/` directory
- [ ] Create `k8s/overlays/` directory with dev/staging/prod subdirectories
- [ ] Create `k8s/base/storage/` directory
- [ ] Directory structure matches planned layout

**Files to Create**:
- `k8s/` (directory structure)

**Notes**:
- Follow Kustomize conventions if using Kustomize
- Structure should support environment overlays

---

### Task 1.2: Create Namespace and Service Accounts
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~1h  
**Dependencies**: Task 1.1  
**Status**: ⏳ Pending

**Description**:
Create Kubernetes namespaces for each environment (dev/staging/prod) and service accounts with IRSA for ECR access.

**Acceptance Criteria**:
- [ ] Create `k8s/base/namespace.yaml` with base namespace structure
- [ ] Create namespaces: `layering-detection-dev`, `layering-detection-staging`, `layering-detection-prod`
- [ ] Create service accounts for each service (orchestrator, layering, wash-trading, aggregator) in base
- [ ] Create IAM roles for service accounts with ECR read permissions
- [ ] Configure IRSA (IAM Roles for Service Accounts) annotations on service accounts
- [ ] Configure RBAC (Role/RoleBinding) if needed for service accounts
- [ ] Service accounts can pull images from ECR via IRSA
- [ ] `kubectl apply -f k8s/base/namespace.yaml` creates namespaces successfully
- [ ] Service accounts are created and can pull images from ECR
- [ ] Document IRSA setup process

**Files to Create**:
- `k8s/base/namespace.yaml`
- `k8s/base/service-accounts.yaml`
- `k8s/base/rbac.yaml` (if needed)
- `k8s/base/irsa-setup.md` (IRSA configuration instructions)

**Notes**:
- IRSA allows service accounts to assume IAM roles without long-lived credentials
- Each service account needs IAM role with ECR read permissions
- Namespaces provide isolation between environments
- Overlays will customize namespaces per environment

---

### Task 1.3: Extract and Create ConfigMaps
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 1.1  
**Status**: ⏳ Pending

**Description**:
Extract environment variables from Terraform ECS configuration and create Kubernetes ConfigMaps.

**Acceptance Criteria**:
- [ ] Review `terraform/ecs.tf` lines 43-102 for environment variables
- [ ] Create `k8s/base/configmap.yaml` with all non-sensitive config
- [ ] ConfigMap includes service URLs (LAYERING_SERVICE_URL, etc.)
- [ ] ConfigMap includes application config (LOG_LEVEL, MAX_RETRIES, etc.)
- [ ] ConfigMap includes rate limits (RATE_LIMIT_PER_MINUTE)
- [ ] ConfigMap includes timeouts (ALGORITHM_TIMEOUT_SECONDS)
- [ ] Separate ConfigMaps per service or single shared ConfigMap
- [ ] `kubectl apply -f k8s/base/configmap.yaml` creates ConfigMaps successfully
- [ ] ConfigMaps are accessible to pods

**Files to Create**:
- `k8s/base/configmap.yaml`

**Files to Review**:
- `terraform/ecs.tf`

**Notes**:
- Do not include secrets in ConfigMaps (use Secrets instead)
- Consider separate ConfigMaps per service for better isolation

---

### Task 1.4: Create Kubernetes Secrets
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 1.1  
**Status**: ⏳ Pending

**Description**:
Set up External Secrets Operator to sync secrets from AWS Secrets Manager. Create ExternalSecret resources for `API_KEY` and `PSEUDONYMIZATION_SALT`.

**Acceptance Criteria**:
- [ ] Install External Secrets Operator in cluster (via Helm or kubectl)
- [ ] Create IAM role for External Secrets Operator with Secrets Manager read permissions
- [ ] Configure IRSA for External Secrets Operator service account
- [ ] Create `k8s/base/external-secrets.yaml` with ExternalSecret resources
- [ ] ExternalSecret for `API_KEY` (for all services)
- [ ] ExternalSecret for `PSEUDONYMIZATION_SALT` (for aggregator only)
- [ ] ExternalSecrets sync secrets from AWS Secrets Manager
- [ ] Secrets are accessible to appropriate pods
- [ ] Document secret management approach
- [ ] `kubectl apply -f k8s/base/external-secrets.yaml` creates ExternalSecrets successfully
- [ ] Verify secrets are synced and accessible in pods

**Files to Create**:
- `k8s/base/external-secrets.yaml`
- `k8s/base/external-secrets-operator-install.md` (installation instructions)

**Notes**:
- External Secrets Operator syncs from existing AWS Secrets Manager
- No need to duplicate secrets or commit to git
- IRSA required for External Secrets Operator to access Secrets Manager
- Secrets are automatically synced and updated when changed in Secrets Manager

---

## Phase 2: Storage Migration

### Task 2.1: Set Up StorageClass for EFS (AWS EKS)
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 1.1  
**Status**: ⏳ Pending

**Description**:
Install EFS CSI driver and create StorageClass for EFS volumes in AWS EKS. Reuse existing EFS file system from ECS deployment.

**Acceptance Criteria**:
- [ ] EFS CSI driver is installed in EKS cluster (or document installation steps)
- [ ] Identify existing EFS file system ID from ECS Terraform configuration
- [ ] Create `k8s/base/storage/storageclass.yaml` with StorageClass `efs-sc`
- [ ] StorageClass uses EFS CSI provisioner
- [ ] StorageClass references existing EFS file system (or creates new one)
- [ ] StorageClass is set as default (optional)
- [ ] `kubectl apply -f k8s/base/storage/storageclass.yaml` creates StorageClass
- [ ] Document EFS CSI driver installation and configuration

**Files to Create**:
- `k8s/base/storage/storageclass.yaml`
- `k8s/base/storage/README.md` (EFS CSI driver installation instructions)

**Files to Review**:
- `terraform/` (to find existing EFS file system ID)

**Notes**:
- EFS CSI driver must be installed before creating PVCs
- Reuse existing EFS file system to maintain data continuity
- EFS supports ReadWriteMany access mode (multiple pods can mount)

---

### Task 2.2: Create PersistentVolumeClaims
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 2.1  
**Status**: ⏳ Pending

**Description**:
Create PersistentVolumeClaims for input, output, and logs directories.

**Acceptance Criteria**:
- [ ] Create `k8s/base/storage/input-pvc.yaml` for input volume (read-only)
- [ ] Create `k8s/base/storage/output-pvc.yaml` for output volume (read-write)
- [ ] Create `k8s/base/storage/logs-pvc.yaml` for logs volume (read-write)
- [ ] PVCs use StorageClass from Task 2.1
- [ ] PVCs request appropriate storage size (e.g., 10Gi, adjust as needed)
- [ ] `kubectl apply -f k8s/base/storage/` creates all PVCs
- [ ] PVCs are bound and ready
- [ ] Document how to use existing EFS file system (if migrating from ECS)

**Files to Create**:
- `k8s/base/storage/input-pvc.yaml`
- `k8s/base/storage/output-pvc.yaml`
- `k8s/base/storage/logs-pvc.yaml`

**Notes**:
- If migrating from ECS, reuse existing EFS file system
- Storage size should match or exceed current usage
- Access modes: ReadWriteMany for EFS, ReadWriteOnce for block storage

---

### Task 2.3: Verify Volume Access and Permissions
**Type**: Infra  
**Priority**: P1 (High)  
**Effort**: ~1h  
**Dependencies**: Task 2.2  
**Status**: ⏳ Pending

**Description**:
Test that volumes are accessible with correct permissions.

**Acceptance Criteria**:
- [ ] Create test pod to mount input-pvc
- [ ] Verify read access to input-pvc at `/app/input`
- [ ] Create test pod to mount output-pvc
- [ ] Verify write access to output-pvc at `/app/output`
- [ ] Create test pod to mount logs-pvc
- [ ] Verify write access to logs-pvc at `/app/logs`
- [ ] Verify file permissions (read-only for input, read-write for output/logs)
- [ ] Document volume access patterns

**Files to Create**:
- `k8s/base/storage/test-pod.yaml` (temporary, for testing)

**Notes**:
- Use `kubectl run` or test pod to verify access
- Check file permissions and ownership
- Clean up test pods after verification

---

## Phase 3: Deployments & Services

### Task 3.1: Create Orchestrator Deployment
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 1.3, Task 1.4, Task 2.2  
**Status**: ⏳ Pending

**Description**:
Convert ECS orchestrator task definition to Kubernetes Deployment.

**Acceptance Criteria**:
- [ ] Create `k8s/services/orchestrator/deployment.yaml`
- [ ] Map CPU/memory from Terraform variables (512 CPU, 1024 MB memory)
- [ ] Set initial replicas to 1 (from `desired_count`)
- [ ] Configure image from ECR/GHCR (use same image as ECS)
- [ ] Mount input-pvc at `/app/input` (read-only)
- [ ] Set environment variables from ConfigMap and Secrets
- [ ] Configure liveness probe: HTTP GET `/health` (interval: 30s, timeout: 10s, initialDelaySeconds: 5)
- [ ] Configure readiness probe: HTTP GET `/health` (interval: 10s, timeout: 5s)
- [ ] Set service account
- [ ] `kubectl apply -f k8s/services/orchestrator/deployment.yaml` creates deployment
- [ ] Pods start successfully and pass health checks

**Files to Create**:
- `k8s/services/orchestrator/deployment.yaml`

**Files to Review**:
- `terraform/ecs.tf` (orchestrator task definition)
- `terraform/variables.tf` (resource limits)

**Notes**:
- Use same container image as ECS deployment
- Health check should match ECS health check behavior
- Resource requests should match ECS task CPU/memory

---

### Task 3.2: Create Algorithm Services Deployments
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~3h  
**Dependencies**: Task 1.3, Task 1.4  
**Status**: ⏳ Pending

**Description**:
Create Kubernetes Deployments for layering and wash-trading services.

**Acceptance Criteria**:
- [ ] Create `k8s/services/layering/deployment.yaml`
- [ ] Create `k8s/services/wash-trading/deployment.yaml`
- [ ] Map CPU/memory from Terraform (512 CPU, 512 MB memory each)
- [ ] Set initial replicas: layering=2, wash-trading=2 (from `desired_count`)
- [ ] Configure images from ECR/GHCR
- [ ] Set environment variables from ConfigMap and Secrets
- [ ] Configure liveness and readiness probes (same as orchestrator)
- [ ] No persistent storage mounts (stateless services)
- [ ] `kubectl apply` creates both deployments successfully
- [ ] Pods start and pass health checks

**Files to Create**:
- `k8s/services/layering/deployment.yaml`
- `k8s/services/wash-trading/deployment.yaml`

**Notes**:
- Algorithm services are stateless (no volume mounts)
- Can scale independently based on load

---

### Task 3.3: Create Aggregator Deployment
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 1.3, Task 1.4, Task 2.2  
**Status**: ⏳ Pending

**Description**:
Create Kubernetes Deployment for aggregator service.

**Acceptance Criteria**:
- [ ] Create `k8s/services/aggregator/deployment.yaml`
- [ ] Map CPU/memory from Terraform (512 CPU, 512 MB memory)
- [ ] Set initial replicas to 1 (from `desired_count`)
- [ ] Configure image from ECR/GHCR
- [ ] Mount output-pvc at `/app/output` (read-write)
- [ ] Mount logs-pvc at `/app/logs` (read-write)
- [ ] Set environment variables from ConfigMap and Secrets (including PSEUDONYMIZATION_SALT)
- [ ] Configure liveness and readiness probes
- [ ] `kubectl apply` creates deployment successfully
- [ ] Pods start and can write to volumes

**Files to Create**:
- `k8s/services/aggregator/deployment.yaml`

**Notes**:
- Aggregator needs write access to output and logs volumes
- Only aggregator needs PSEUDONYMIZATION_SALT secret

---

### Task 3.4: Create ClusterIP Services
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~1h  
**Dependencies**: Task 3.1, Task 3.2, Task 3.3  
**Status**: ⏳ Pending

**Description**:
Create ClusterIP services for internal service-to-service communication.

**Acceptance Criteria**:
- [ ] Create `k8s/services/orchestrator/service.yaml` (ClusterIP, port 8000)
- [ ] Create `k8s/services/layering/service.yaml` (ClusterIP, port 8001)
- [ ] Create `k8s/services/wash-trading/service.yaml` (ClusterIP, port 8002)
- [ ] Create `k8s/services/aggregator/service.yaml` (ClusterIP, port 8003)
- [ ] Services select correct deployment pods
- [ ] Service names match DNS names used in environment variables
- [ ] `kubectl apply` creates all services successfully
- [ ] Services resolve via DNS (test with `kubectl run` test pod)
- [ ] Orchestrator can reach algorithm services via service names

**Files to Create**:
- `k8s/services/orchestrator/service.yaml`
- `k8s/services/layering/service.yaml`
- `k8s/services/wash-trading/service.yaml`
- `k8s/services/aggregator/service.yaml`

**Notes**:
- Service names must match URLs in orchestrator ConfigMap
- DNS format: `http://<service-name>:<port>` (same namespace)

---

### Task 3.5: Create Ingress Resource
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 3.4  
**Status**: ⏳ Pending

**Description**:
Replace ALB with Kubernetes Ingress resource using AWS Load Balancer Controller for external access.

**Acceptance Criteria**:
- [ ] AWS Load Balancer Controller is installed in EKS cluster (or document installation steps)
- [ ] Create IAM role for AWS Load Balancer Controller with ALB permissions
- [ ] Configure IRSA for AWS Load Balancer Controller service account
- [ ] Create `k8s/ingress/ingress.yaml` with IngressClass annotation for AWS ALB
- [ ] Route `/orchestrate*`, `/health`, `/` to orchestrator service
- [ ] Optionally route other paths to respective services (if needed)
- [ ] Configure TLS termination for production (cert-manager + ACM)
- [ ] Set up cert-manager with ACM issuer (for TLS)
- [ ] `kubectl apply -f k8s/ingress/ingress.yaml` creates Ingress
- [ ] AWS Load Balancer Controller creates ALB automatically
- [ ] External access works via ALB DNS name
- [ ] Health checks accessible via Ingress

**Files to Create**:
- `k8s/ingress/ingress.yaml`
- `k8s/ingress/aws-load-balancer-controller-install.md` (installation instructions)

**Files to Review**:
- `terraform/alb.tf` (ALB routing rules)

**Notes**:
- AWS Load Balancer Controller must be installed before creating Ingress
- Controller automatically creates ALB when Ingress is created
- IRSA required for controller to create/manage ALBs
- For TLS, use cert-manager with ACM issuer (IRSA integration)
- Start with HTTP in dev, add TLS for staging/prod

---

## Phase 4: Auto-Scaling

### Task 4.1: Create HorizontalPodAutoscaler for All Services
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 3.1, Task 3.2, Task 3.3  
**Status**: ⏳ Pending

**Description**:
Replace ECS auto-scaling with Kubernetes HorizontalPodAutoscaler (HPA).

**Acceptance Criteria**:
- [ ] Create `k8s/services/orchestrator/hpa.yaml`
- [ ] Create `k8s/services/layering/hpa.yaml`
- [ ] Create `k8s/services/wash-trading/hpa.yaml`
- [ ] Create `k8s/services/aggregator/hpa.yaml`
- [ ] Configure CPU target: 70% (from Terraform autoscaling.tf)
- [ ] Configure memory target: 80% (from Terraform autoscaling.tf)
- [ ] Set min replicas from `min_capacity` variable (orchestrator: 1, layering: 1, wash-trading: 1, aggregator: 1)
- [ ] Set max replicas from `max_capacity` variable (orchestrator: 5, layering: 10, wash-trading: 10, aggregator: 5)
- [ ] Configure scale-down stabilization: 5 minutes (300s)
- [ ] Configure scale-up stabilization: 1 minute (60s)
- [ ] Metrics server is installed and working
- [ ] `kubectl apply` creates all HPAs successfully
- [ ] HPAs scale pods based on CPU/memory utilization

**Files to Create**:
- `k8s/services/orchestrator/hpa.yaml`
- `k8s/services/layering/hpa.yaml`
- `k8s/services/wash-trading/hpa.yaml`
- `k8s/services/aggregator/hpa.yaml`

**Files to Review**:
- `terraform/autoscaling.tf` (ECS auto-scaling configuration)
- `terraform/variables.tf` (min/max capacity)

**Notes**:
- Metrics server must be installed for HPA to work
- HPA requires resource requests/limits to be set in deployments
- Test scaling by generating load

---

## Phase 5: Monitoring & Logging

### Task 5.1: Set Up Logging (CloudWatch or Native)
**Type**: Infra  
**Priority**: P1 (High)  
**Effort**: ~3h  
**Dependencies**: Task 3.1, Task 3.2, Task 3.3  
**Status**: ⏳ Pending

**Description**:
Configure Fluent Bit DaemonSet to collect logs and send to CloudWatch Logs via IRSA.

**Acceptance Criteria**:
- [ ] Install Fluent Bit DaemonSet in EKS cluster
- [ ] Create IAM role for Fluent Bit with CloudWatch Logs write permissions
- [ ] Configure IRSA for Fluent Bit service account
- [ ] Create `k8s/monitoring/fluent-bit.yaml` with Fluent Bit configuration
- [ ] Configure log collection from all service pods (stdout/stderr)
- [ ] Configure CloudWatch Log Groups (reuse existing from ECS: `/ecs/${app_name}/${service}`)
- [ ] Logs include service name and request_id (structured logging)
- [ ] Log retention matches ECS configuration (7 days default)
- [ ] Logs are sent to CloudWatch Log Groups
- [ ] Logs are viewable in CloudWatch Console
- [ ] Document Fluent Bit setup and configuration

**Files to Create**:
- `k8s/monitoring/fluent-bit.yaml`
- `k8s/monitoring/fluent-bit-config.yaml` (ConfigMap for Fluent Bit config)
- `k8s/monitoring/fluent-bit-install.md` (installation instructions)

**Files to Review**:
- `terraform/ecs.tf` (CloudWatch Log Groups configuration)

**Notes**:
- Fluent Bit uses IRSA to write to CloudWatch Logs (no long-lived credentials)
- Reuse existing CloudWatch Log Groups from ECS for consistency
- Fluent Bit is lightweight and efficient for log collection

---

### Task 5.2: Set Up Metrics Collection
**Type**: Infra  
**Priority**: P1 (High)  
**Effort**: ~3h  
**Dependencies**: Task 3.1, Task 3.2, Task 3.3  
**Status**: ⏳ Pending

**Description**:
Enable CloudWatch Container Insights for metrics collection in EKS.

**Acceptance Criteria**:
- [ ] Enable Container Insights on EKS cluster (via cluster add-on or CloudWatch agent)
- [ ] Create IAM role for CloudWatch agent with CloudWatch metrics write permissions
- [ ] Configure IRSA for CloudWatch agent service account (if using agent)
- [ ] Container Insights collects CPU, memory, and pod count metrics
- [ ] Metrics are viewable in CloudWatch Console
- [ ] Metrics match ECS CloudWatch metrics (CPUUtilization, MemoryUtilization, RunningTaskCount)
- [ ] Create CloudWatch dashboard for service metrics (reuse existing dashboard structure)
- [ ] Document Container Insights setup

**Files to Create**:
- `k8s/monitoring/cloudwatch-insights-config.yaml` (if manual configuration needed)
- `k8s/monitoring/cloudwatch-dashboard.yaml` (CloudWatch dashboard definition)

**Files to Review**:
- `terraform/monitoring.tf` (CloudWatch alarms and dashboard)

**Notes**:
- Container Insights is native to EKS and requires minimal setup
- Can be enabled via EKS cluster add-on or CloudWatch agent DaemonSet
- Metrics automatically appear in CloudWatch Console
- Reuse existing CloudWatch dashboard structure from ECS

---

### Task 5.3: Set Up Alarms/Alerting
**Type**: Infra  
**Priority**: P1 (High)  
**Effort**: ~2h  
**Dependencies**: Task 5.2  
**Status**: ⏳ Pending

**Description**:
Replicate CloudWatch alarms in Kubernetes monitoring system.

**Acceptance Criteria**:
- [ ] Review `terraform/monitoring.tf` for alarm definitions
- [ ] Create PrometheusAlertManager rules (if using Prometheus)
- [ ] Or configure CloudWatch alarms for K8s metrics (if using CloudWatch)
- [ ] Alarms for high CPU (threshold: 80%)
- [ ] Alarms for high memory (threshold: 85%)
- [ ] Alarms for low pod count (threshold: < 1)
- [ ] Alerts are sent to notification channel (email, Slack, PagerDuty)
- [ ] Test alarms by generating load

**Files to Create**:
- `k8s/monitoring/alerts.yaml` (if using Prometheus)
- `k8s/monitoring/cloudwatch-alarms.yaml` (if using CloudWatch)

**Files to Review**:
- `terraform/monitoring.tf` (alarm definitions)

**Notes**:
- Match alarm thresholds from ECS CloudWatch alarms
- Configure alerting channels appropriately

---

## Phase 6: CI/CD Updates

### Task 6.1: Update GitHub Actions for K8s Deployment
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~3h  
**Dependencies**: All previous phases  
**Status**: ⏳ Pending

**Description**:
Update GitHub Actions workflow to deploy to EKS cluster after image build. Use ECR for images and Kustomize for environment overlays.

**Acceptance Criteria**:
- [ ] Review `.github/workflows/ci.yml` for current deployment steps
- [ ] Add K8s deployment job (after ECR image build/push)
- [ ] Configure `kubectl` in GitHub Actions with EKS cluster access
- [ ] Set up EKS cluster access (kubeconfig via GitHub Secrets or OIDC)
- [ ] Configure AWS credentials for EKS access (via GitHub Secrets or OIDC)
- [ ] Deploy to appropriate namespace (dev/staging/prod based on branch) using Kustomize overlays
- [ ] Use Kustomize for environment-specific configs (`k8s/overlays/{env}/`)
- [ ] Deployment job runs after successful ECR image build
- [ ] Deployment updates existing resources (rolling update via `kubectl apply`)
- [ ] Update image tags in deployments (use commit SHA or tag)
- [ ] Document deployment process and EKS access setup

**Files to Modify**:
- `.github/workflows/ci.yml`

**Files to Review**:
- `.github/workflows/ci.yml` (current CI/CD pipeline)
- `terraform/ecr.tf` (ECR repository configuration)

**Notes**:
- Use `kubectl apply` with Kustomize for deployments
- EKS access via OIDC is preferred (no long-lived credentials)
- Or use GitHub Secrets for kubeconfig (less secure)
- Kustomize overlays allow environment-specific customization
- Image tags should use commit SHA or semantic versioning

---

### Task 6.2: Create Environment-Specific Overlays
**Type**: Infra  
**Priority**: P1 (High)  
**Effort**: ~2h  
**Dependencies**: Task 6.1  
**Status**: ⏳ Pending

**Description**:
Create Kustomize overlays for dev/staging/prod environments with separate namespaces.

**Acceptance Criteria**:
- [ ] Create `k8s/overlays/dev/` with dev-specific configs
- [ ] Create `k8s/overlays/staging/` with staging-specific configs
- [ ] Create `k8s/overlays/prod/` with prod-specific configs
- [ ] Each overlay sets namespace: `layering-detection-dev`, `layering-detection-staging`, `layering-detection-prod`
- [ ] Overlays customize replica counts, resource limits, or configs per environment
- [ ] Dev: Lower replica counts, smaller resource limits
- [ ] Staging: Similar to prod but with test data
- [ ] Prod: Full replica counts and resource limits
- [ ] CI/CD uses appropriate overlay based on branch/environment
- [ ] Document overlay usage and namespace strategy

**Files to Create**:
- `k8s/overlays/dev/kustomization.yaml`
- `k8s/overlays/dev/namespace.yaml` (if namespace not in base)
- `k8s/overlays/staging/kustomization.yaml`
- `k8s/overlays/staging/namespace.yaml`
- `k8s/overlays/prod/kustomization.yaml`
- `k8s/overlays/prod/namespace.yaml`

**Notes**:
- Kustomize overlays allow environment-specific customization
- Separate namespaces provide isolation between environments
- Single cluster with multiple namespaces is cost-effective
- Can customize any resource (replicas, limits, configs) per environment

---

## Phase 7: Testing & Validation

### Task 7.1: End-to-End Testing in Dev Environment
**Type**: Test  
**Priority**: P0 (Critical)  
**Effort**: ~4h  
**Dependencies**: All previous phases  
**Status**: ⏳ Pending

**Description**:
Test full pipeline execution in Kubernetes dev environment.

**Acceptance Criteria**:
- [ ] Deploy all services to dev namespace
- [ ] Upload test input CSV to input volume
- [ ] Trigger orchestrator endpoint via Ingress
- [ ] Verify algorithm services process events
- [ ] Verify aggregator merges results and writes output files
- [ ] Verify output CSV files are created correctly
- [ ] Verify logs are written correctly
- [ ] Compare results with ECS deployment (if available)
- [ ] Document test results

**Files to Create**:
- `k8s/tests/e2e-test.md` (test procedure)

**Notes**:
- Use same test data as ECS deployment
- Verify output format matches ECS output

---

### Task 7.2: Performance and Load Testing
**Type**: Test  
**Priority**: P1 (High)  
**Effort**: ~3h  
**Dependencies**: Task 7.1  
**Status**: ⏳ Pending

**Description**:
Test performance and auto-scaling behavior under load.

**Acceptance Criteria**:
- [ ] Generate load on services (using load testing tool)
- [ ] Verify HPA scales pods up based on CPU/memory
- [ ] Verify HPA scales pods down when load decreases
- [ ] Measure response times and compare with ECS
- [ ] Verify no performance degradation vs ECS
- [ ] Document performance test results

**Notes**:
- Use tools like `kubectl run` with load generator or dedicated load testing tool
- Monitor HPA behavior and pod scaling

---

### Task 7.3: Rollback Testing
**Type**: Test  
**Priority**: P1 (High)  
**Effort**: ~2h  
**Dependencies**: Task 7.1  
**Status**: ⏳ Pending

**Description**:
Test rollback procedure to ECS if needed.

**Acceptance Criteria**:
- [ ] Document rollback procedure
- [ ] Test switching traffic back to ECS (if dual deployment)
- [ ] Verify ECS services are still functional
- [ ] Document rollback steps

**Files to Create**:
- `k8s/ROLLBACK.md` (rollback procedure)

**Notes**:
- Rollback should be quick and safe
- Keep ECS infrastructure until K8s is fully validated

---

## Summary

### Task Count by Phase

- **Phase 1 (Core Resources)**: 4 tasks
- **Phase 2 (Storage)**: 3 tasks
- **Phase 3 (Deployments & Services)**: 5 tasks
- **Phase 4 (Auto-Scaling)**: 1 task
- **Phase 5 (Monitoring & Logging)**: 3 tasks
- **Phase 6 (CI/CD)**: 2 tasks
- **Phase 7 (Testing & Validation)**: 3 tasks

**Total**: 21 tasks

### Estimated Effort

- **Phase 1**: ~5.5 hours
- **Phase 2**: ~5 hours
- **Phase 3**: ~10 hours
- **Phase 4**: ~2 hours
- **Phase 5**: ~8 hours
- **Phase 6**: ~5 hours
- **Phase 7**: ~9 hours

**Total**: ~44.5 hours (~5-6 days for one developer)

### Critical Path

1. Core Resources (Tasks 1.1-1.4) → All services depend on this
2. Storage (Tasks 2.1-2.3) → Deployments need volumes
3. Deployments & Services (Tasks 3.1-3.5) → Core functionality
4. Auto-Scaling (Task 4.1) → Production readiness
5. CI/CD (Tasks 6.1-6.2) → Deployment automation
6. Testing (Tasks 7.1-7.3) → Validation

### Parallelization Opportunities

- **Phase 1**: ConfigMaps and Secrets can be created in parallel
- **Phase 2**: All PVCs can be created in parallel
- **Phase 3**: All service deployments can be created in parallel (after base resources)
- **Phase 5**: Logging and metrics can be set up in parallel

### Risk Mitigation

- **High Risk**: Storage migration (Task 2.1-2.3) - test thoroughly with existing data
- **Medium Risk**: Ingress configuration (Task 3.5) - ensure external access works
- **Low Risk**: ConfigMaps/Secrets (Tasks 1.3-1.4) - straightforward conversion

### Dependencies & Prerequisites

**Before Starting**:
- **AWS EKS cluster** (Kubernetes 1.24+) with IRSA enabled
- `kubectl` configured with EKS cluster access
- **AWS Load Balancer Controller** installed
- **EFS CSI driver** installed
- **Metrics server** installed (for HPA)
- **External Secrets Operator** installed
- **Fluent Bit** DaemonSet installed (for CloudWatch logging)
- **ECR access** configured (IRSA for service accounts)
- Existing **EFS file system** (reuse from ECS)
- Existing **Secrets Manager secrets** (API_KEY, PSEUDONYMIZATION_SALT)

**AWS IAM Prerequisites**:
- IAM roles for service accounts (IRSA) for:
  - ECR image pull access
  - CloudWatch Logs write access (Fluent Bit)
  - Secrets Manager read access (External Secrets Operator)
  - ALB create/manage access (AWS Load Balancer Controller)
  - CloudWatch metrics write access (Container Insights)

**Tools**:
- `kubectl` (configured for EKS)
- `kustomize` (for environment overlays)
- `helm` (for External Secrets Operator installation)
- `aws` CLI (for EKS cluster access)
