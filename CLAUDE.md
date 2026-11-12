# Meeting Notes AI

The app started as a take-home assignment and is now being prepared for production
as an internal company tool for user interviews with players and coaches (product
feedback), used mainly by one colleague. Work is split into numbered GitHub issues
(014 onwards), one branch per issue. Where an issue conflicts with what this file
says about the app, the issue wins and this file is updated as part of the issue.

## What the app does now
A small single-user web app (no login, no user accounts):
1. The user selects a video file (at least MP4) in the React UI and uploads it.
2. The FastAPI backend converts it to an MP3 audio file (ffmpeg).
3. Google Gemini transcribes the MP3, then generates a title, a short summary, key
   topics and action items (with the responsible person when the meeting mentions it).
4. All results are stored in the database; a meeting can be processed again.

- The UI shows how far processing has got: uploading → upload finished →
  transcription → summary and action items → done (or failed, with an error message).
- Meetings list (name, date, number of action items, View button) and meeting
  details (information, transcription, summary, action items), with loading,
  processing, error and empty states.
- Errors are returned with proper HTTP status codes; API keys come only from
  environment variables.

## Approach
- AI provider: Google Gemini (Python SDK `google-genai`).
- Database: MySQL in Docker (`docker-compose.yml` with only the `db` service for now).
- Frontend: React + Vite, JavaScript (not TypeScript).
- Processing is slow, so the upload returns immediately, processing runs in the
  background, the status is stored in the database and the frontend polls for it.

## Project structure
- backend/ – FastAPI app, Python virtual environment in backend/.venv
- backend/tests/ – pytest tests; shared fixtures in backend/tests/conftest.py
- frontend/ – React + Vite (JavaScript)

## Commands
- Backend: `cd backend`, then `fastapi dev app/main.py` (http://localhost:8000/docs)
- Backend tests: `cd backend`, then `pytest` (the database must be running;
  dev tools are installed with `pip install -r requirements-dev.txt`)
- Backend lint: `cd backend`, then `ruff check .`
- Frontend: `cd frontend`, then `npm run dev` (http://localhost:5173)

## Working rules
- The developer is new to Python, FastAPI and React: explain new concepts and changes.
- Work in small steps and explain what was changed and why after each change.
- Ask before adding a new dependency or changing the project structure.
- Do nothing outside the scope of the current task.
- Never read, print or modify `.env` files. API keys never go into code or documentation.
- Never put real interviews (recordings, transcripts, summaries, interviewee names)
  into tests, fixtures, examples, logs or documentation; use made-up data only.
- Every change to the database models comes with an Alembic migration; never edit a
  migration that has already been applied.
- Every issue adds or changes backend tests for what it changes, and `pytest` must
  pass at the end of the issue. Tests never call Gemini or ffmpeg: they use the mocks
  from `backend/tests/conftest.py`.
- Never run commands that create, change or delete Google Cloud resources unless
  explicitly asked.
- Never commit or push unless explicitly asked.
- Write explanations in Serbian (Latin script); code, comments, commit messages and
  documentation in English.