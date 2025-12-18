# Layering Detection Analytics

Python-based batch analytics that scans intraday transactions data (`input/transactions.csv`) to detect suspicious manipulation patterns (layering and wash trading) and produces:

- `output/suspicious_accounts.csv` – one row per detected suspicious sequence (see [Output Format](#output-format) below).
- `logs/detections.csv` – per-sequence detection logs (account, product, sequence of order timestamps, and duration in seconds), with columns:
  - `account_id`
  - `product_id`
  - `order_timestamps`
  - `duration_seconds`

The implementation follows the PRD in `assignment` and the specs in `specs/`.

---

## Quick Start (5 minutes)

### Option 1: Microservices (Recommended for Production)

**Prerequisites:** Docker and Docker Compose

```powershell
# Start all services
docker-compose up --build

# In another terminal, trigger pipeline
curl -X POST http://localhost:8000/orchestrate -H "Content-Type: application/json" -d '{"input_file": "input/transactions.csv"}'

# Check outputs
ls output/suspicious_accounts.csv
ls logs/detections.csv

# Stop services
docker-compose down
```

### Option 2: Monolithic (Development/Testing)

**Prerequisites:** Python 3.11+

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .
python main.py
```

---

## Architecture

The system uses a **microservices architecture** with independent services communicating via REST APIs. Each service runs in its own Docker container, enabling independent scaling, deployment, and fault isolation.

### System Flow

```
CSV Input → Orchestrator → [Algorithm Services (parallel)] → Aggregator → Output
```

### Architecture Diagram

```mermaid
graph TD
    A[CSV Input<br/>transactions.csv] -->|read| B[Orchestrator Service<br/>:8000]
    B -->|POST /detect<br/>request_id + events| C[Layering Service<br/>:8001]
    B -->|POST /detect<br/>request_id + events| D[Wash Trading Service<br/>:8002]
    C -->|SuspiciousSequence[]| B
    D -->|SuspiciousSequence[]| B
    B -->|POST /aggregate<br/>all results + metadata| E[Aggregator Service<br/>:8003]
    E -->|write| F[suspicious_accounts.csv]
    E -->|write| G[detections.csv]
    
    subgraph "Docker Compose Network"
        B
        C
        D
        E
    end
    
    subgraph "Algorithm Services"
        C
        D
    end
    
    style C fill:#e1f5ff
    style D fill:#e1f5ff
    style B fill:#fff4e1
    style E fill:#e8f5e9
```

### Services

**1. Orchestrator Service** (`services/orchestrator-service/`)
- **Port:** 8000
- **Responsibilities:** Read CSV, generate request IDs, call algorithm services in parallel, handle retries, forward to aggregator
- **Endpoints:** `POST /orchestrate`, `GET /health`
- **Features:** Retry logic with exponential backoff, fault isolation, completion tracking

**2. Layering Service** (`services/layering-service/`)
- **Port:** 8001
- **Responsibilities:** Run layering detection algorithm
- **Endpoints:** `POST /detect`, `GET /health`
- **Features:** Idempotent operations, result caching

**3. Wash Trading Service** (`services/wash-trading-service/`)
- **Port:** 8002
- **Responsibilities:** Run wash trading detection algorithm
- **Endpoints:** `POST /detect`, `GET /health`
- **Features:** Idempotent operations, result caching

**4. Aggregator Service** (`services/aggregator-service/`)
- **Port:** 8003
- **Responsibilities:** Validate completion, merge results, write CSV files
- **Endpoints:** `POST /aggregate`, `GET /health`
- **Features:** Completion validation, result deduplication, CSV writing

### Design Principles

- **Separation of Concerns:** Each service has a single responsibility
- **Fault Isolation:** Service failures don't cascade
- **Independent Scaling:** Scale algorithm services independently based on load
- **Parallel Execution:** Algorithm services run concurrently
- **Idempotency:** Retries don't cause duplicate processing
- **Type Safety:** Strict type hints with Pydantic validation at service boundaries

---

## Migration from Monolith

The system migrated from a monolithic architecture to microservices to address scalability, fault isolation, and independent deployment needs.

### Migration Status

- ✅ Microservices architecture implemented
- ✅ All services containerized
- ✅ Docker Compose orchestration configured
- ✅ Backward compatibility maintained (monolithic mode still available)

### When to Use Each Architecture

**Microservices (Recommended):**
- Production deployments requiring scalability
- Independent algorithm scaling needs
- Fault isolation requirements
- High availability requirements
- Parallel algorithm execution

**Monolithic (Still Available):**
- Development/testing (simpler setup)
- Small-scale deployments
- Single-machine execution
- Rapid prototyping

### Performance Comparison

| Aspect | Monolithic | Microservices |
|--------|-----------|---------------|
| Network Latency | Zero (in-process) | ~10-50ms per service call |
| Execution | Sequential (sum of times) | Parallel (max of times) |
| Scaling | Single point | Independent per service |
| Fault Isolation | None (single failure point) | Per-service isolation |
| **Net Benefit** | Simpler, faster for small workloads | Better for production, parallelization typically outweighs network overhead |

### Migration Path

The migration was completed in phases:

1. **Phase 1:** Extracted algorithm services (Layering, Wash Trading)
2. **Phase 2:** Implemented orchestrator service with retry logic
3. **Phase 3:** Implemented aggregator service for result validation and merging
4. **Phase 4:** Configured Docker Compose for full pipeline orchestration

**Backward Compatibility:** The monolithic `main.py` CLI remains functional, calling `layering_detection.orchestrator.run_pipeline()` directly. Both architectures produce identical output formats.

---

## Project Structure

```
Layering-Detection-Analytics/
├── services/                    # Microservices
│   ├── orchestrator-service/   # Pipeline coordination
│   ├── layering-service/       # Layering detection algorithm
│   ├── wash-trading-service/   # Wash trading detection algorithm
│   ├── aggregator-service/     # Result aggregation and CSV writing
│   └── shared/                 # Shared utilities (API models, converters, logging)
├── src/layering_detection/      # Core domain models and algorithms
│   ├── models.py               # Domain models (TransactionEvent, SuspiciousSequence)
│   ├── algorithms/             # Detection algorithms
│   ├── detectors/              # Algorithm implementations
│   └── utils/                  # Utilities (I/O, logging, security)
├── input/transactions.csv      # Sample input file
├── output/                     # Output directory (created at runtime)
├── logs/                       # Logs directory (created at runtime)
├── tests/                      # pytest-based unit, integration, and e2e tests
├── specs/                      # Architecture and feature specifications
├── docker-compose.yml          # Docker Compose configuration
├── main.py                     # Monolithic CLI entry point (backward compatibility)
└── pyproject.toml              # Python package configuration
```

---

## Requirements

- Python **3.11** (for monolithic mode)
- Docker and Docker Compose (for microservices mode)
- `pip` (up-to-date inside virtual environment)

---

## Local Setup and Installation

### Microservices Setup

**Using Docker Compose (Recommended):**

```powershell
# Build and start all services
docker-compose up --build

# Services will be available at:
# - Orchestrator: http://localhost:8000
# - Layering: http://localhost:8001
# - Wash Trading: http://localhost:8002
# - Aggregator: http://localhost:8003

# Check health
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

**Running Individual Services Locally:**

Each service can be run independently for development:

```powershell
# Layering Service
cd services/layering-service
python -m pip install -r requirements.txt
uvicorn main:app --port 8001

# Wash Trading Service
cd services/wash-trading-service
python -m pip install -r requirements.txt
uvicorn main:app --port 8002

# Aggregator Service
cd services/aggregator-service
python -m pip install -r requirements.txt
uvicorn main:app --port 8003

# Orchestrator Service
cd services/orchestrator-service
python -m pip install -r requirements.txt
uvicorn main:app --port 8000
```

### Monolithic Setup

From the project root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .
```

Ensure the input file is present at:
- `input\transactions.csv`

---

## Running the Solution

### Microservices Mode (Recommended)

**Using Docker Compose:**

```powershell
# Start all services
docker-compose up --build

# Trigger pipeline execution
curl -X POST http://localhost:8000/orchestrate `
  -H "Content-Type: application/json" `
  -d '{\"input_file\": \"input/transactions.csv\"}'

# Or use PowerShell's Invoke-RestMethod
$body = @{ input_file = "input/transactions.csv" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/orchestrate -Method POST -Body $body -ContentType "application/json"
```

**Using Python Client:**

```python
import httpx

response = httpx.post(
    "http://localhost:8000/orchestrate",
    json={"input_file": "input/transactions.csv"}
)
print(response.json())
```

**Outputs:**
- `output/suspicious_accounts.csv`
- `logs/detections.csv`

### Monolithic Mode (Backward Compatibility)

With the virtual environment activated:

```powershell
python main.py
```

Or with custom paths:

```powershell
python main.py input/transactions.csv output logs
```

**Programmatic:**

```powershell
python -c "from pathlib import Path; from layering_detection.orchestrator import run_pipeline; run_pipeline(Path('input/transactions.csv'), Path('output'), Path('logs'))"
```

---

## Running Tests

With the virtual environment activated:

```powershell
python -m pip install pytest pytest-asyncio
pytest
```

**Test Structure:**
- `tests/unit/` – Unit tests for individual components
- `tests/integration/` – Integration tests for service interactions
- `tests/e2e/` – End-to-end tests with Docker Compose

**Run specific test suites:**

```powershell
pytest tests/unit/                    # Unit tests only
pytest tests/integration/             # Integration tests only
pytest tests/e2e/                     # End-to-end tests only
pytest tests/unit/test_orchestrator_validation.py  # Specific test file
```

---

## Running via Docker

### Microservices (Docker Compose)

Build and run all services:

```powershell
docker-compose up --build
```

This starts all four services with:
- Health checks configured
- Volumes mounted (`input/`, `output/`, `logs/`)
- Network configured for inter-service communication
- Automatic restarts on failure

**Stop services:**

```powershell
docker-compose down
```

**View logs:**

```powershell
docker-compose logs -f orchestrator-service
docker-compose logs -f layering-service
docker-compose logs -f wash-trading-service
docker-compose logs -f aggregator-service
```

### Monolithic (Single Container)

Build the monolithic Docker image:

```powershell
docker build -t layering-detection:0.1.0 -t layering-detection:latest .
```

Run the container:

```powershell
docker run --rm `
  -v ${PWD}\input:/app/input `
  -v ${PWD}\output:/app/output `
  -v ${PWD}\logs:/app/logs `
  layering-detection:0.1.0
```

---

## Output Format

### `suspicious_accounts.csv`

The output CSV contains one row per detected suspicious sequence. The schema includes:

**Required Columns (all detection types):**
- `account_id`: Suspicious account identifier
- `product_id`: Product where activity was detected
- `total_buy_qty`: Total BUY quantity during the pattern window (integer)
- `total_sell_qty`: Total SELL quantity during the pattern window (integer)
- `num_cancelled_orders`: Count of cancelled orders in the sequence
  - For **LAYERING**: Actual count of cancelled orders (≥3)
  - For **WASH_TRADING**: Always 0 (not applicable to wash trading)
- `detected_timestamp`: ISO datetime when detection occurred
  - For **LAYERING**: Timestamp of the opposite-side trade that completes the pattern
  - For **WASH_TRADING**: Timestamp of the last trade in the 30-minute window

**Additional Columns (for multi-algorithm support):**
- `detection_type`: Type of detection pattern (`"LAYERING"` or `"WASH_TRADING"`)

**Wash Trading Specific Columns (empty for LAYERING):**
- `alternation_percentage`: Percentage of side switches between consecutive trades (decimal, 2 places)
  - Empty string (`""`) for LAYERING detections
  - Only populated for WASH_TRADING when ≥60% alternation is detected
- `price_change_percentage`: Price change during the detection window (decimal, 2 places)
  - Empty string (`""`) if:
    - Detection type is LAYERING (not applicable)
    - Price change is <1% (optional bonus threshold not met)
  - Only populated for WASH_TRADING when price change ≥1% (optional bonus criterion)

**Example Output:**
```csv
account_id,product_id,total_buy_qty,total_sell_qty,num_cancelled_orders,detected_timestamp,detection_type,alternation_percentage,price_change_percentage
ACC001,IBM,3000,2000,3,2025-01-15T10:30:00Z,LAYERING,,
ACC002,GOOG,12000,12000,0,2025-01-15T11:00:00Z,WASH_TRADING,80.00,1.25
```

**Note:** The assignment specification defines 6 core columns. The additional columns (`detection_type`, `alternation_percentage`, `price_change_percentage`) are included to support wash trading detection, which is also specified in the assignment requirements.

---

## Outputs Delivered

After a successful run (microservices or monolithic), you should have:

- `output\` folder containing:
  - `suspicious_accounts.csv` (see [Output Format](#output-format) above)
- `logs\` folder containing:
  - `detections.csv`

You can package these along with a screenshot of the running Docker container and this project as the final delivery.

---

## Assumptions

- **Time semantics**:
  - All timestamps in `transactions.csv` are UTC ISO datetimes with a trailing `Z` (e.g. `2025-10-26T10:21:20Z`).
  - Detection windows (10s for orders, 5s for cancels, 2s for opposite trades) are evaluated using these parsed datetimes.
- **Order identity**:
  - Input rows do not contain explicit order IDs; we approximate "orders cancelled before execution" purely from event type, side, and timing.
  - Partially executed orders are not modeled explicitly; we rely on the simplified PRD and timing-only interpretation.
- **Input quality**:
  - Invalid rows (bad types, invalid enums, missing fields) are rare and can be skipped with a warning; they do not abort the run.
  - `account_id` and `product_id` come from trusted upstream systems and are not attacker-controlled in typical deployments.
- **Scope of detection**:
  - Only the 3-step simplified layering pattern from the PRD is implemented; no additional market-abuse scenarios are covered.
  - Each order is intended to participate in at most one detected sequence for a given `(account_id, product_id)` group.

---

## Possible Improvements / Extensions

- **Richer order modeling**:
  - Introduce explicit order IDs and execution quantities if the upstream data supports them, to distinguish fully/partially executed vs. purely cancelled orders more accurately.
  - Track per-order lifecycle to identify more complex behaviors (e.g., layered spoofing with partial fills).
- **Detection engine flexibility**:
  - Make timing thresholds (10s/5s/2s) configurable via a simple config file or environment variables.
  - Support additional patterns (e.g., multi-level price layering, cross-product patterns) behind clear feature flags.
- **Performance & scalability**:
  - For very large `transactions.csv` files, move from in-memory lists to streaming/grouped processing or chunked reads.
  - Consider parallelizing detection across accounts/products if/when CPU-bound.
  - Add horizontal scaling support for algorithm services (load balancing).
- **Operational hardening**:
  - Replace basic `logging` setup with a configurable logging configuration (JSON logs, log rotation, different sinks).
  - Add more robust error reporting for malformed inputs (summary statistics, counts per error type).
  - Add distributed tracing (OpenTelemetry) for request tracking across services.
- **Security & privacy**:
  - Expose a configuration switch to always pseudonymize account IDs in logs (and possibly outputs) for environments with stricter privacy requirements.
  - Extend CSV sanitization to any additional free-text fields if the schema grows in the future.
  - Add authentication/authorization for service endpoints in production.

---

## Notes on Using Cursor for This Project

This repository was developed using the **Cursor** IDE with AI assistance wired into the project workspace. The AI assistant was configured to:

- Read and respect the specification files under `specs/` and the original `assignment` text.
- Make incremental code changes directly in `src/` and `tests/`, keeping the codebase always in a runnable state.
- Run semantic and grep-style searches across the workspace to understand and refactor code.
- Use **specialized agents** (e.g., `@agent.pm.md`, `@agent.architect.md`, `@agent.reviewer.md`, `@agent.tester.md`, `@agent.security.md`, `@agent.devops.md`, `@agent.docs.md`) for different tasks such as planning, architecture, code review, testing, security review, DevOps/Docker, and documentation.
