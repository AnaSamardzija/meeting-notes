# Meeting Notes AI

A small single-user web app for meeting recordings. You upload a video, the
backend extracts the audio with ffmpeg, Google Gemini transcribes it and writes
a summary, the key topics and the action items, and everything is stored in a
MySQL database so the processed meetings can be opened again later.

## Project structure

```
backend/    FastAPI application (Python)
frontend/   React + Vite application (JavaScript)
```

The database runs in Docker; the backend and the frontend run locally, each in
its own terminal.

## Prerequisites

- Python 3.14
- Node.js 24 (with npm)
- Docker Desktop (for the database)
- ffmpeg (the backend uses it to extract the audio from the uploaded video)
- A Google Gemini API key

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

## 1. Environment variables

The project uses two `.env` files, each created from its `.env.example`. Run
these from the project root:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env
Copy-Item frontend/.env.example frontend/.env

# macOS / Linux
cp .env.example .env
cp frontend/.env.example frontend/.env
```

### Root `.env` (database and backend)

Set your own passwords and your Gemini API key; the other values can stay as
they are.

| Variable                 | Default                 | Description                                               |
|--------------------------|-------------------------|-----------------------------------------------------------|
| `MYSQL_DATABASE`         | required                | Database name                                             |
| `MYSQL_USER`             | required                | Database user                                             |
| `MYSQL_PASSWORD`         | required                | Password of the database user                             |
| `MYSQL_ROOT_PASSWORD`    | required                | Password of the MySQL root user (used by Docker only)     |
| `DB_HOST`                | `localhost`             | Host of the database                                      |
| `DB_PORT`                | `3306`                  | Port of the database on your machine                      |
| `CORS_ORIGINS`           | `http://localhost:5173` | Origins that are allowed to call the API, comma-separated |
| `LOG_LEVEL`              | `INFO`                  | Lowest level of the log messages the backend prints       |
| `UPLOAD_DIR`             | `uploads`               | Folder for uploaded videos, relative to `backend/`        |
| `MAX_UPLOAD_MB`          | `500`                   | Largest video that can be uploaded, in megabytes          |
| `FFMPEG_TIMEOUT_SECONDS` | `600`                   | Longest time ffmpeg may take on one video, in seconds     |
| `GEMINI_API_KEY`         | required                | Google Gemini API key                                     |
| `GEMINI_MODEL`           | `gemini-3.8-flash`      | Gemini model for the transcription and the summary        |
| `GEMINI_TIMEOUT_SECONDS` | `600`                   | Longest time one request to Gemini may take, in seconds   |

The backend does not start if a required variable is missing.

### `frontend/.env`

| Variable             | Example                 | Description                                                            |
|----------------------|-------------------------|------------------------------------------------------------------------|
| `VITE_API_URL`       | `http://localhost:8000` | Base URL of the backend API                                            |
| `VITE_MAX_UPLOAD_MB` | `500`                   | Largest video the form accepts, in megabytes; same as `MAX_UPLOAD_MB` |

Variables with the `VITE_` prefix are embedded in the JavaScript that is sent to
the browser, so they are public: never put secrets in `frontend/.env`. Restart
`npm run dev` after changing this file.

## 2. Database

Run these from the project root, with Docker Desktop running:

```bash
docker compose up -d
docker compose ps
```

The database is ready when the status shows `healthy`. If it does not get there,
check the logs with `docker compose logs db`.

Stop the database:

```bash
docker compose down      # removes the container, the data is kept
docker compose down -v   # removes the container and deletes all data
```

Notes:

- The `MYSQL_*` values are applied only on the first start, when the volume is
  empty. If you change them in `.env` later, run `docker compose down -v` and
  start the database again (this deletes the data).
- If port 3306 is already in use on your machine, change `DB_PORT` in `.env`.

## 3. Backend

Run these from the `backend/` folder, with the database running.

Create and activate a virtual environment:

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies, create the database tables and start the development
server:

```bash
pip install -r requirements.txt
alembic upgrade head
fastapi dev app/main.py
```

- Swagger documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health (returns `503` if the database
  is not available)

### Database migrations

The tables are created with [Alembic](https://alembic.sqlalchemy.org/)
migrations, stored in `backend/alembic/versions/`. Run these from the `backend/`
folder, with the virtual environment activated:

```bash
alembic upgrade head     # apply all migrations that are not applied yet
alembic current          # show which migration the database is on
alembic downgrade -1     # undo the last migration
alembic downgrade base   # undo all migrations (drops the tables and their data)
```

## 4. Frontend

Run these from the `frontend/` folder:

```bash
npm install
npm run dev
```

Open http://localhost:5173.

## Using the app

1. Click **Upload meeting**, choose a video (`.mp4`, `.mov`, `.webm` or `.mkv`)
   and click **Upload**.
2. The meeting appears on the list. Its status changes by itself while it is
   processed: Uploaded, Transcribing, Summarizing, Done (or Failed).
3. Click **View** to see the transcript, the summary, the key topics and the
   action items. A failed meeting shows the reason and a **Try again** button.
