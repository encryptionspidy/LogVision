#!/usr/bin/env bash

# Source virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Detect and kill process on port 5000
if lsof -ti:5000 >/dev/null 2>&1; then
    echo "Port 5000 is occupied. Freeing..."
    lsof -ti:5000 | xargs kill -9
    sleep 1
fi

echo "Starting backend..."
export DEV_MODE=1 
exec python -m gunicorn "api.server:create_app()" --bind 0.0.0.0:5000
