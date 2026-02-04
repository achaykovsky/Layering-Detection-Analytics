# GitHub Actions CI/CD Workflows

This directory contains GitHub Actions workflows for continuous integration and deployment.

## Workflows

### `ci.yml` - Main CI Pipeline

Comprehensive CI pipeline that runs on every push and pull request.

#### Stages (in order):

1. **Lint & Type Check** (`lint`)
   - Fastest stage, fails early
   - Checks code formatting and type hints
   - Runs on Ubuntu latest

2. **Unit Tests** (`unit-tests`)
   - Runs pytest unit tests
   - Tests on Python 3.11 and 3.12
   - Generates coverage reports
   - Uploads coverage to Codecov (Python 3.11 only)

3. **Integration Tests** (`integration-tests`)
   - Runs integration tests
   - Requires unit tests to pass first
   - Tests service interactions without Docker Compose

4. **Build Docker Images** (`build-images`)
   - Builds Docker images for all services:
     - `orchestrator-service`
     - `layering-service`
     - `wash-trading-service`
     - `aggregator-service`
   - Does not push (images used for Trivy and local testing).
   - Uses BuildKit cache for faster builds.

5. **Push to ECR** (`push-to-ecr`, optional)
   - Runs on push to `main`, `develop`, or `staging` when AWS credentials are set.
   - Builds and pushes each service image to AWS ECR with tags: commit SHA and branch name.
   - Requires: AWS OIDC (`AWS_ROLE_ARN`) or static credentials; variables: `AWS_REGION`, `ECR_REPOSITORY_PREFIX`.
   - See [EKS-DEPLOY.md](EKS-DEPLOY.md) for setup.

6. **Deploy to EKS** (`deploy-k8s`, optional)
   - Runs after successful `push-to-ecr` when `EKS_CLUSTER_NAME` is set.
   - Configures kubectl for EKS, builds Kustomize overlay (dev/staging/prod from branch), substitutes ECR image URIs (commit SHA), applies manifest.
   - Branch → overlay: `main` → prod, `develop` → dev, `staging` → staging.
   - **Production deploy gate**: Deploys from `main` use the **production** GitHub Environment and require approval (or wait timer) if configured. Deploys from `develop`/`staging` use the **development** environment and run without approval. See [Production deploy approval](#production-deploy-approval) below.
   - See [EKS-DEPLOY.md](EKS-DEPLOY.md) for EKS access and deployment process.

7. **Security Scan** (`security-scan`)
   - Runs Trivy vulnerability scanner on built images
   - Uploads results to GitHub Security tab
   - Only runs on non-PR events (after images are pushed)

8. **E2E Tests** (`e2e-tests`)
   - Runs end-to-end tests with Docker Compose
   - Builds and starts all services
   - Waits for health checks
   - Runs full pipeline tests
   - Skips if `[skip e2e]` is in commit message

9. **CI Summary** (`ci-summary`)
   - Generates summary of all job results
   - Always runs (even if other jobs fail)

#### Features

- **Fail Fast**: Lint and unit tests run first
- **Parallel Execution**: Unit tests run in parallel across Python versions
- **Caching**: Poetry dependencies and Docker layers are cached
- **Security**: Automated vulnerability scanning with Trivy
- **Conditional Execution**: E2E tests can be skipped with `[skip e2e]` in commit message
- **Image Tagging**: Images tagged with commit SHA, branch, and semantic versions

#### Skipping E2E Tests

To skip E2E tests (e.g., for documentation-only changes), include `[skip e2e]` in your commit message:

```bash
git commit -m "Update README [skip e2e]"
```

#### Production deploy approval

Deploys to the **prod** overlay (from branch `main`) use the GitHub **production** environment. Deploys from `develop` or `staging` use the **development** environment and run without a gate.

To require approval or a wait timer before production deploys:

1. In the repo: **Settings → Environments**.
2. Create an environment named **production** (and optionally **development** for non-main; if missing, GitHub creates it when the job runs).
3. In **production**:
   - **Required reviewers**: Add one or more users/teams who must approve before the deploy job runs.
   - **Wait timer**: Optionally set a delay (e.g. 5 minutes) before the job can proceed.
4. When someone pushes to `main`, the workflow runs; after `push-to-ecr` succeeds, the **Deploy to EKS** job waits for the production environment. Approvers see a pending deployment in the Actions run and can approve or reject.

Without configuring **production**, the job still runs (no approval). Configure the environment to enforce an approval gate.

#### Manual Workflow Trigger

You can manually trigger the workflow from the GitHub Actions tab:
1. Go to Actions → CI
2. Click "Run workflow"
3. Select branch and click "Run workflow"

## Environment Variables

The workflow uses the following environment variables:

- `PYTHON_VERSION`: Python version to use (default: "3.11")
- `REGISTRY`: Container registry URL (default: "ghcr.io")
- `IMAGE_PREFIX`: Prefix for image names (default: repository name)

## Secrets

- `GITHUB_TOKEN`: Automatically provided (for SARIF upload, etc.).

For **ECR push and EKS deploy** (optional):

- **Repo variables** (Settings → Secrets and variables → Actions → Variables):
  - `ECR_PUSH_ENABLED`: Set to `true` when AWS credentials are configured (enables push-to-ecr and deploy-k8s).
  - `USE_AWS_OIDC`: Set to `true` when using OIDC (`AWS_ROLE_ARN`); set to `false` or leave unset when using static credentials (unset is treated as static for backward compatibility). If unset and static secrets are missing, the static-credentials step fails with a clear error.
- **Secrets**: **OIDC**: `AWS_ROLE_ARN`. **Static**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
- **Variables**: `AWS_REGION`, `ECR_REPOSITORY_PREFIX`, `EKS_CLUSTER_NAME`.

See [EKS-DEPLOY.md](EKS-DEPLOY.md).

## Container Registry

Images are pushed to GitHub Container Registry (ghcr.io) with the following naming:

```
ghcr.io/<repository>/<service-name>:<tag>
```

Example:
```
ghcr.io/username/layering-detection-analytics-orchestrator-service:main-abc1234
```

## Best Practices

1. **Keep PRs focused**: Smaller PRs run faster through CI
2. **Fix linting early**: Address linting issues before running full test suite
3. **Use [skip e2e] sparingly**: E2E tests catch integration issues
4. **Monitor security scans**: Review Trivy results in GitHub Security tab
5. **Check CI summary**: Review the summary job output for quick status overview

## Troubleshooting

### Tests failing locally but passing in CI

- Ensure you're using the same Python version (3.11+)
- Check that Poetry dependencies are up to date: `poetry lock --no-update`
- Verify Docker Compose version matches CI

### Docker build failures

- Check Dockerfile syntax
- Verify all required files are in the build context
- Review build logs for specific error messages

### E2E tests timing out

- Increase timeout in workflow if needed
- Check service health check configuration
- Review Docker Compose logs for startup issues

### Security scan failures

- Review Trivy results in GitHub Security tab
- Update vulnerable dependencies: `poetry update <package>`
- Consider using `--ignore-unfixed` flag if false positives
