# Stateful Cache-Aware Router for Distributed LLM Inference

## Overview
This project implements a **Stateful Cache-Aware Router** for distributed Large Language Model (LLM) serving. It addresses the "Cache Blindness" problem in standard load balancers by routing requests to workers that already hold the relevant Key-Value (KV) cache, significantly reducing Time-To-First-Token (TTFT) for RAG and Chat workloads.

## Architecture
- **Router (`router/`)**: A FastAPI service that tracks global cache state and routes requests using a "Sticky-Least-Loaded" policy.
- **Worker Patch (`vllm_patch/`)**: Modifications to vLLM to enable "Push-Based" eviction reporting.
- **Consistency Protocol**: A hybrid mechanism using real-time eviction reports (Fast Path) and periodic anti-entropy sync (Slow Path).

## Directory Structure
- `router/`: Source code for the Router service.
- `vllm_patch/`: Source code for the vLLM sidecar/patch.
- `scripts/`: Test scripts (`mock_worker.py`, `benchmark.py`).
- `docs/`: Technical reports and documentation (`report.pdf`).

## Setup & Usage

### Prerequisites
- Python 3.8+
- `fastapi`, `uvicorn`, `aiohttp`, `transformers`

### Running the Router
```bash
python -m router.main
```

### Running the Mock Worker (Simulation)
```bash
python scripts/mock_worker.py
```

### Running the Benchmark
```bash
python scripts/benchmark.py
```

## Documentation
See `docs/report.pdf` for the detailed technical report.
