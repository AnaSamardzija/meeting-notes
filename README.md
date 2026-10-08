# Meeting Notes AI

A small web app that takes a recorded meeting, transcribes it with an AI API and
generates a summary and a list of action items.

This README covers the basic local setup and will be extended as the project grows.

## Project structure

```
backend/    FastAPI application (Python)
frontend/   React + Vite application (JavaScript)
```

## Prerequisites

- Python 3.14
- Node.js 24 (with npm)

## Backend

All commands are run from the `backend/` folder.

Create and activate a virtual environment:

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies and start the development server:

```bash
pip install -r requirements.txt
fastapi dev app/main.py
```

- API: http://localhost:8000/
- Swagger documentation: http://localhost:8000/docs

## Frontend

All commands are run from the `frontend/` folder.

```bash
npm install
npm run dev
```

- App: http://localhost:5173/

The backend and the frontend run independently, each in its own terminal.
