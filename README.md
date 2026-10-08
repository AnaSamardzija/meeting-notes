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
- ffmpeg (the backend uses it to extract the audio from the uploaded video)

Install ffmpeg and make sure it is on the `PATH`:

```bash
# Windows (PowerShell)
winget install Gyan.FFmpeg

# macOS
brew install ffmpeg

# Linux (Debian / Ubuntu)
sudo apt install ffmpeg
```

Open a new terminal and check the installation:

```bash
ffmpeg -version
```

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

The backend reads its configuration from the same `.env` file in the project
root that is used for the database (see above):

| Variable                 | Default                 | Description                                               |
|--------------------------|-------------------------|-----------------------------------------------------------|
| `MYSQL_DATABASE`         | required                | Database name                                             |
| `MYSQL_USER`             | required                | Database user                                             |
| `MYSQL_PASSWORD`         | required                | Password of the database user                             |
| `DB_HOST`                | `localhost`             | Host of the database                                      |
| `DB_PORT`                | `3306`                  | Port of the database                                      |
| `CORS_ORIGINS`           | `http://localhost:5173` | Origins that are allowed to call the API, comma-separated |
| `UPLOAD_DIR`             | `uploads`               | Folder for uploaded videos, relative to `backend/`        |
| `MAX_UPLOAD_MB`          | `500`                   | Largest video that can be uploaded, in megabytes          |
| `FFMPEG_TIMEOUT_SECONDS` | `600`                   | Longest time ffmpeg may take on one video, in seconds     |
| `GEMINI_API_KEY`         | required                | Google Gemini API key                                     |
| `GEMINI_MODEL`           | `gemini-3.8-flash`      | Gemini model for the transcription and the summary        |

The backend builds the database URL from these values, so the password is
written in one place only.

Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey)
and set it as `GEMINI_API_KEY` in `.env`. The backend does not start without it.

Install the dependencies, create the database tables and start the development
server (the database must be running):

```bash
pip install -r requirements.txt
alembic upgrade head
fastapi dev app/main.py
```

- Health check: http://localhost:8000/api/health
- Swagger documentation: http://localhost:8000/docs

The health check also tests the database connection. It returns `200` with
`{"status": "ok", "database": "ok"}`, or `503` if the database is not available.

### Database migrations

The tables are created and changed with [Alembic](https://alembic.sqlalchemy.org/)
migrations, stored in `backend/alembic/versions/`. Alembic takes the database
connection from the same `.env` file as the backend, not from `alembic.ini`.

Run these from the `backend/` folder, with the virtual environment activated and
the database running:

```bash
alembic upgrade head     # apply all migrations that are not applied yet
alembic current          # show which migration the database is on
alembic downgrade -1     # undo the last migration
alembic downgrade base   # undo all migrations (drops the tables and their data)
```

After changing a model in `app/models.py`, generate a new migration, review the
generated file and apply it:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Frontend

All commands are run from the `frontend/` folder.

Create the frontend `.env` file from the example:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

| Variable       | Example                 | Description                 |
|----------------|-------------------------|-----------------------------|
| `VITE_API_URL` | `http://localhost:8000` | Base URL of the backend API |

Variables with the `VITE_` prefix are embedded in the JavaScript that is sent to
the browser, so they are public: never put secrets in `frontend/.env`. Restart
`npm run dev` after changing this file.

Install the dependencies and start the development server:

```bash
npm install
npm run dev
```

- App: http://localhost:5173/

The home page shows whether the backend is reachable and whether the backend can
reach the database. Open the app at
`http://localhost:5173` (not `http://127.0.0.1:5173`), because that is the origin
allowed by `CORS_ORIGINS`.

The backend and the frontend run independently, each in its own terminal.
