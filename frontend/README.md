# LogVision Frontend

Next.js investigation UI for LogVision.

## Run

```bash
cd frontend
npm install

# If backend runs on localhost:5000 (default)
npm run dev

# If backend runs elsewhere
NEXT_PUBLIC_API_URL=http://localhost:5000 npm run dev
```

Open http://localhost:3000.

## Build

```bash
npm run lint
npm run build
npm run start
```

## Notes

- The frontend calls backend endpoints from `frontend/lib/api.ts`.
- Default backend URL is `http://localhost:5000` unless `NEXT_PUBLIC_API_URL` is set.
- If UI shows API error states, start backend first from the repo root:

```bash
source .venv/bin/activate
DEV_MODE=1 python -m gunicorn "api.server:create_app()" --bind 0.0.0.0:5000
```
