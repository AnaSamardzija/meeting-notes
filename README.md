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
- Docker Desktop (for the database)

## Database

MySQL runs in a Docker container. Only the database is dockerized for now; the
backend and the frontend run locally. All commands are run from the project root,
with Docker Desktop running.

Create your `.env` file from the example and set your own passwords in it:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Start the database and check that it is ready:

```bash
docker compose up -d
docker compose ps
```

The database is ready when the status shows `healthy`. If it does not get there,
check the logs with `docker compose logs db`.

Connection details:

| Setting  | Value                                      |
|----------|--------------------------------------------|
| Host     | `localhost`                                |
| Port     | `DB_PORT` from `.env` (3306 by default)    |
| Database | `MYSQL_DATABASE` from `.env`               |
| User     | `MYSQL_USER` from `.env`                   |
| Password | `MYSQL_PASSWORD` from `.env`               |

Stop the database:

```bash
docker compose down      # removes the container, the data is kept
docker compose down -v   # removes the container and deletes all data
```

Notes:

- The data is stored in a Docker volume, so it survives `docker compose down`.
- The `MYSQL_*` values are applied only on the first start, when the volume is
  empty. If you change them in `.env` later, run `docker compose down -v` and
  start the database again (this deletes the data).
- If port 3306 is already in use on your machine, change `DB_PORT` in `.env`.

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
