# LogVision — Intelligent Observability Platform

A production-grade log analysis system with multi-engine anomaly detection, root cause analysis, event timeline visualization, and an organic modern dashboard.

```
 ┌────────────┐     ┌──────────┐     ┌───────────┐     ┌──────────┐     ┌────────────┐
 │  Ingestion │────▶│ Parsing  │────▶│ Detection │────▶│ Scoring  │────▶│ Root Cause │
 │ File/JSON  │     │ (Multi)  │     │ (3-engine)│     │ Severity │     │  Timeline  │
 └────────────┘     └──────────┘     └───────────┘     └──────────┘     └────────────┘
```

## Features

| Category | Details |
|---|---|
| **Detection** | 3-engine anomaly system: rule-based, Isolation Forest ML, z-score statistical |
| **Root Cause** | Template-based grouping, cascade failure detection, correlation scoring |
| **Timeline** | Chronological event bucketing with automatic spike detection |
| **Clustering** | TF-IDF + MiniBatchKMeans log grouping, Drain-style template extraction |
| **Ingestion** | Plain text, JSON Lines, Bunyan/Pino, directory watching, syslog (stub) |
| **Workers** | Async analysis via ThreadPoolExecutor with job tracking |
| **Metrics** | Self-observability: latency percentiles, error rate, throughput, queue backlog |
| **Storage** | SQLite persistence via SQLAlchemy, full-text search |
| **Security** | JWT auth, RBAC, Pydantic input validation, secure cookies, HSTS, rate limiting |
| **Dashboard** | Next.js organic modern UI with Recharts, Framer Motion, React Query |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm 9+

### Backend

```bash
# Clone and setup
git clone <repo-url> && cd log_analyzer
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run API server (development mode — auth bypassed)
DEV_MODE=1 python -m gunicorn "api.server:create_app()" --bind 0.0.0.0:5000

# Run API server (production mode — auth enforced)
ENV=production JWT_SECRET=your-secret-min-32-chars python -m gunicorn "api.server:create_app()" --bind 0.0.0.0:5000
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # Development server at http://localhost:3000
npm run build        # Production build
```

### Docker

```bash
docker build -t logvision .

# Production
docker run -p 5000:5000 -e JWT_SECRET=your-secret-min-32-chars logvision

# Development (auth bypassed)
docker run -p 5000:5000 -e DEV_MODE=1 logvision
```

---

## API Reference

### Public Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System health check |
| `GET` | `/search?q=&severity=&limit=&offset=` | Search logs with filters |
| `GET` | `/analytics?hours=24` | Dashboard metrics |
| `GET` | `/alerts/config` | Alert rule configuration |
| `GET` | `/timeline?hours=6&bucket=15` | Chronological anomaly timeline |
| `GET` | `/root-cause?hours=24&min_group=2` | Grouped root cause analysis |
| `GET` | `/metrics` | System performance metrics |
| `POST` | `/login` | Get JWT token |

### Protected Endpoints (Require `Authorization: Bearer <token>`)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/analyze` | `admin` | Synchronous log analysis |
| `POST` | `/analyze/async` | `admin` | Async analysis (returns job ID) |
| `GET` | `/job/<id>/status` | `admin` | Check async job progress |
| `POST` | `/token/refresh` | any | Refresh JWT token |

### Example Usage

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","role":"admin"}' | jq -r .token)

# Analyze a log file
curl -X POST http://localhost:5000/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/var/log/syslog"

# Async analysis
JOB=$(curl -s -X POST http://localhost:5000/analyze/async \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/var/log/syslog" | jq -r .job_id)

# Poll job status
curl http://localhost:5000/job/$JOB/status -H "Authorization: Bearer $TOKEN"

# View timeline
curl http://localhost:5000/timeline?hours=6

# View root causes
curl http://localhost:5000/root-cause?hours=24

# System metrics
curl http://localhost:5000/metrics
```

---

## Architecture

```
log_analyzer/
├── api/server.py              # Flask API (18 endpoints)
├── app/
│   ├── anomaly/               # 3-engine detection (rule + ML + stats)
│   ├── clustering/            # TF-IDF + Drain template mining
│   ├── root_cause/            # Aggregator + cascade correlation
│   ├── timeline/              # Bucketed event timeline + spike detection
│   ├── worker/                # ThreadPoolExecutor job queue
│   ├── ingestion/             # Multi-source: text, JSON, directory watcher
│   ├── metrics/               # System self-metrics collector
│   ├── security/              # JWT auth, RBAC, Pydantic validators
│   ├── severity/              # Deterministic severity scoring
│   ├── parsing/               # Multi-format log parser
│   └── config/                # Application settings
├── config/                    # Environment configs (base/dev/prod)
├── frontend/                  # Next.js organic modern dashboard
├── tests/                     # 235 tests
└── scripts/
    ├── evaluate_accuracy.py   # P/R/F1 evaluation
    └── benchmark.py           # Performance benchmarking
```

---

## Testing

```bash
# Activate venv first
source venv/bin/activate

# Full suite (235 tests)
pytest tests/ -v --cov=app --cov-report=term-missing

# By module
pytest tests/test_root_cause.py -v       # Root cause (21 tests)
pytest tests/test_timeline.py -v         # Timeline (11 tests)
pytest tests/test_worker.py -v           # Worker queue (9 tests)
pytest tests/test_ingestion_multi.py -v  # Multi-source ingestion (15 tests)
pytest tests/test_metrics.py -v          # System metrics (12 tests)
pytest tests/test_security.py -v         # Security (14 tests)
pytest tests/test_clustering.py -v       # Clustering (20 tests)

# Accuracy evaluation
python scripts/evaluate_accuracy.py --generate-synthetic
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ENV` | `development` | `production` enables strict security |
| `JWT_SECRET` | *(dev key)* | Token signing secret (≥32 chars in prod) |
| `JWT_EXPIRY_HOURS` | `24` | Token lifetime |
| `DEV_MODE` | `0` | `1` bypasses auth for testing |
| `DB_PATH` | `logs.db` | SQLite database path |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `MAX_WORKERS` | `4` | Background worker thread pool size |
| `MONITOR_ENABLED` | `false` | Enable real-time file monitoring |
| `MONITOR_LOG_PATH` | — | File path for real-time monitoring |

---

## License

MIT
