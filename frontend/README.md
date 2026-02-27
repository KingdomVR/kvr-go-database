# KVR Go — Frontend

This is a minimal Node.js frontend and proxy for the KVR Go Python API.

Quick start:

1. Copy your API key into environment variable `KVR_API_KEY` and ensure the Python API is running (default http://localhost:5000).

2. From this folder:

```bash
cd frontend
npm install
npm start
```

3. Open http://localhost:3000

Environment variables:
- `KVR_API_KEY` — required, the API key used to call the Python backend.
- `KVR_BACKEND_URL` — optional, default `http://localhost:5000`.
- `FRONTEND_PORT` — optional, default `3000`.
- `SESSION_SECRET` — optional, session secret.
