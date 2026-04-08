# LogVision - AI-Powered Log Intelligence Assistant

An intelligent log analysis system with a chat-driven interface for analyzing logs, detecting anomalies, and providing AI-powered insights.

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- npm or yarn

### 1. Backend Setup

```bash
# Activate Python virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies (if not already installed)
pip install -r requirements.txt

# Start the backend server
DEV_MODE=1 python -m gunicorn 'api.server:create_app()' --bind 0.0.0.0:5000
```

The API will be available at `http://localhost:5000`

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Project Structure

```
log_analyzer/
├── api/                    # Flask API server
│   └── server.py          # Main API endpoints
├── app/                   # Core Python application
│   ├── config/           # Configuration
│   ├── ingestion/        # Log file reading
│   ├── parsing/          # Log parsing
│   ├── anomaly/          # Anomaly detection
│   ├── severity/         # Severity scoring
│   ├── explanation/      # Explanation generation
│   ├── llm/              # LLM integration
│   ├── storage/          # Database
│   └── ...
├── frontend/              # Next.js frontend
│   ├── app/              # Next.js app directory
│   ├── components/       # React components
│   ├── lib/              # Utilities
│   └── package.json      # Dependencies
├── components/            # Shared React components (legacy)
├── models/               # Data models/schemas
├── tests/                # Test suite
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve web UI |
| `/health` | GET | Health check |
| `/analyze` | POST | Upload and analyze log file |
| `/analyze/async` | POST | Async analysis with job tracking |
| `/api/analysis/start` | POST | Start new chat-driven analysis |
| `/api/analysis/<id>` | GET | Get analysis session |
| `/api/analysis/<id>/chat` | POST | Send follow-up question |
| `/api/analysis/history` | GET | Get all sessions |
| `/search` | GET | Search persistent logs |
| `/analytics` | GET | Get dashboard metrics |
| `/timeline` | GET | Anomaly timeline |
| `/root-cause` | GET | Grouped root cause events |
| `/job/<id>/status` | GET | Async job status |
| `/metrics` | GET | System metrics |
| `/login` | POST | Generate JWT token (dev mode: any username) |

## Environment Variables

Create a `.env` file in the project root:

```bash
# Flask
DEV_MODE=1                    # Development mode (skips auth)
LOG_LEVEL=DEBUG              # Logging level
DB_PATH=logs.db              # SQLite database path

# Frontend (in frontend/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:5000
```

## Key Features

- **Chat-Driven Analysis**: Upload logs and ask questions in natural language
- **AI-Powered Insights**: LLM-generated explanations and recommendations
- **Anomaly Detection**: Automatic detection of unusual log patterns
- **Session History**: Persistent chat sessions with full history
- **Real-time Updates**: Live insights panel with metrics and charts
- **Security Analysis**: Automatic threat detection in logs

## Development Commands

### Backend
```bash
# Run with development settings
DEV_MODE=1 LOG_LEVEL=DEBUG python -m gunicorn 'api.server:create_app()' --bind 0.0.0.0:5000

# Run tests
python -m pytest tests/
```

### Frontend
```bash
cd frontend

# Development server
npm run dev

# Build for production
npm run build

# Production server
npm start
```

## Troubleshooting

### Port Already in Use
```bash
# Kill process on port 5000
kill $(lsof -t -i:5000)

# Or use different port
DEV_MODE=1 python -m gunicorn 'api.server:create_app()' --bind 0.0.0.0:5001
```

### Frontend Build Errors
```bash
cd frontend
rm -rf .next node_modules package-lock.json
npm install
npm run build
```

### Database Issues
Delete `logs.db` to reset the database (all history will be lost).

## Technology Stack

**Backend:**
- Python 3.10+
- Flask + Gunicorn
- SQLite (persistent storage)
- JWT authentication

**Frontend:**
- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- Recharts (visualization)
- React Query (data fetching)

## License

MIT License
