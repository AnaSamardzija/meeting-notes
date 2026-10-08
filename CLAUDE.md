# Meeting Notes AI

Take-home assignment for a junior developer position. A small single-user web app
(no login, no user accounts): the user uploads a recorded meeting, the backend
extracts the audio, an AI API transcribes it and generates a summary and action
items, everything is stored in a database, and the React UI shows previously
processed meetings and their details.

## Requirements (from the assignment)

### Processing flow
1. The user selects a video file (at least MP4) in the React UI and uploads it.
2. The FastAPI backend receives the video and converts it to an MP3 audio file (ffmpeg).
3. The MP3 is sent to the Google Gemini API to get the transcription.
4. From the transcription, the AI generates a concise meeting summary and a list of action items.
5. All results are stored in the database.

The UI must show how far processing has got: uploading → upload finished →
transcription → summary and action items → done (or failed, with an error message).

### Meeting summary (example; exact format is up to us)
    Meeting Summary
    The team discussed the upcoming product release, current development
    progress, and several outstanding technical issues.
    Key topics:
    - Product release timeline
    - Backend performance
    - Customer feedback
    - Open technical issues

### Action items (example)
Keep the person responsible for an action item when the meeting mentions it.

    Action Items
    - John: Investigate the API performance issue
    - Sarah: Prepare the release documentation
    - Mark: Schedule a follow-up meeting with the client

### Persistence
Store at least: meeting/video ID, original filename, upload date, transcription,
summary, action items, processing status. The user must be able to come back
later and see previously processed meetings.

### UI
- Meetings list: previously uploaded meetings (name, date, number of action items, View button).
- Meeting details: meeting information, transcription, summary, action items.
- Handle loading, processing, error and empty states.
- Simple but usable; functionality matters more than visuals.

### Backend
- FastAPI, with endpoints for uploading a video, listing meetings, getting a meeting
  and processing a meeting (exact API design is up to us).
- Proper error handling and HTTP status codes.
- API keys are never hardcoded; they come from environment variables.

### Bonus (only after the core features work)
- Search through processed meetings (transcription, summary, action items).
- Docker: start the whole app (frontend, backend, database) with `docker compose up`.
- Automated tests for the important backend parts.

### Technical expectations and deliverables
- Reasonable structure, clear separation of frontend and backend, common errors
  handled, secrets kept out of the repository, runnable locally by another developer.
- Deliver: GitHub repo, README with setup and run instructions, `.env.example`,
  database setup/migrations, and a short note on AI usage (tools used, which AI
  provider and why, what was AI-generated or assisted, interesting problems and solutions).
- In the review the developer may be asked to explain or change parts of the code,
  so understanding the code matters more than the amount of code.

## Approach
- AI provider: Google Gemini (Python SDK `google-genai`).
- Database: MySQL in Docker (`docker-compose.yml` with only the `db` service for now;
  the full app is dockerized later as a bonus).
- Frontend: React + Vite, JavaScript (not TypeScript).
- Processing is slow, so the upload returns immediately, processing runs in the
  background, the status is stored in the database and the frontend polls for it.
- Work is split into numbered GitHub issues (000, 001, ...), one branch per issue.

## Project structure
- backend/ – FastAPI app, Python virtual environment in backend/.venv
- frontend/ – React + Vite (JavaScript)

## Commands
- Backend: `cd backend`, then `fastapi dev app/main.py` (http://localhost:8000/docs)
- Frontend: `cd frontend`, then `npm run dev` (http://localhost:5173)

## Working rules
- The developer is new to Python, FastAPI and React: explain new concepts and changes.
- Work in small steps and explain what was changed and why after each change.
- Ask before adding a new dependency or changing the project structure.
- Do nothing outside the scope of the current task.
- Never read, print or modify `.env` files. API keys never go into code or documentation.
- Never commit or push unless explicitly asked.
- Write explanations in Serbian (Latin script); code, comments, commit messages and
  documentation in English.