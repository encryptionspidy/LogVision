# Log Analyzer AI

A high-performance Log Analysis toolkit with an intelligent AI chatbot powered by Gemini & Groq. Identifies anomalies, clusters logs dynamically, mapping errors quickly.

## Features
- **AI-Powered Analysis**: Switch seamlessly between `gemini-1.5-flash` and `llama-3.1-8b-instant`.
- **Intelligent Chat Context**: Engage with your log data with persistent chat history.
- **Vercel-Inspired UI**: Beautiful, minimalistic Peach + Black dark mode design built in Next.js & Tailwind.
- **Python Backend Pipeline**: Robust anomaly detection, summarization, and REST API.

## Requirements
- Python 3.12+
- Node.js 18+

## Quick Start

### Backend Setup
create virtual environment:
```bash
python -m venv .venv
```
activate:
```bash
source .venv/bin/activate
```
install dependencies:
```bash
pip install -r requirements.txt
```

### Environment Variables
create `.env`:
```env
GEMINI_API_KEY=
GROQ_API_KEY=

DEV_MODE=1
```

### Start Backend
```bash
DEV_MODE=1 python -m gunicorn "api.server:create_app()" --bind 0.0.0.0:5000
```

### Start Frontend
```bash
cd frontend
npm install
npm run dev
```

### Test API
```bash
curl http://localhost:5000/health
```
