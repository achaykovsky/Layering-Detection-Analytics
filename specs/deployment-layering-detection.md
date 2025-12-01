# Deployment and Packaging – Layering Detection

## Overview
Defines how to package the layering detection solution as a Python package, build a Docker image, and run the solution while producing outputs in `output/` and logs in `logs/`.

## Requirements
- [ ] Package the solution as an installable Python package (e.g., `pip install .`).
- [ ] Build a Docker image that installs the package and runs the detection.
- [ ] Ensure the container writes:
  - Output CSV files to a local `output/` folder.
  - Logs to a local `logs/` folder.
- [ ] Provide a README with clear, tested “How to run” instructions (local + Docker).
- [ ] Enable simple reproduction on another machine with minimal setup.

## Acceptance Criteria
- [ ] `pip install .` (or equivalent) succeeds without errors.
- [ ] A single documented command runs the full pipeline locally (using the installed package).
- [ ] `docker build` completes successfully and produces an image capable of running the solution.
- [ ] Running the documented Docker command:
  - Creates/uses `output/` and `logs/` directories on the host (via volume/bind mount).
  - Produces `output/suspicious_accounts.csv`.
  - Produces at least one log file in `logs/` describing suspicious detections.
- [ ] README includes setup, run, and troubleshooting sections.

## Technical Details
- Python packaging:
  - Use `pyproject.toml` or `setup.py` for package metadata.
- Docker:
  - Base image: official Python image (slim), Python 3.11+.
  - Multi-stage build if dependencies are heavy.
  - Install package via `pip install .`.
- File system layout inside container:
  - Mount host project directory or `input/`, `output/`, `logs/` individually.
  - Ensure relative paths (e.g., `input/transactions.csv`) are resolved correctly.

## Questions/Clarifications
- Any specific Docker registry or image naming conventions required?
- Any constraints on Python version or base image (e.g., Alpine vs Debian)?
- Should logs be rotated or is a simple file-per-run log sufficient?

## Related Specs
- `specs/requirements-layering-detection.md`
- `specs/feature-layering-detection.md`
- `specs/data-layering-detection.md`


