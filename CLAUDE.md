# Meeting Notes AI

The app started as a take-home assignment and is now being prepared for production
as an internal company tool for user interviews with players and coaches (product
feedback), used mainly by one colleague. Work is split into numbered GitHub issues
(014 onwards), one branch per issue. Where an issue conflicts with what this file
says about the app, the issue wins and this file is updated as part of the issue.

## What the app does now
A small single-user web app (no login, no user accounts):
1. The user selects a video file (at least MP4) in the React UI, can give it a
   title (optional, at most 255 characters) and uploads it.
2. The FastAPI backend converts it to an MP3 audio file (ffmpeg).
3. Google Gemini transcribes the MP3 in the language that is spoken (the main
   interviewer is labelled Jørgen unless the recording shows otherwise; other
   speakers by name, or as Interviewer / Interviewee), then writes,
   always in English, a title (used only when the interview has none) and the
   interview summary the team uses: the
   interviewee (name, role and location, only when said), the takeaway (how well
   the product fits the person; paying and usage when mentioned), the context (who
   they are, how they train or work, which tools they use), and likes, dislikes and
   wants (items with a short title and an explanation; wants ordered by importance).
   Nothing is invented: a section with no content stays empty. Both prompts get a
   short description of SportAI's products and of who usually leads the
   interviews (`COMPANY_CONTEXT` in `backend/app/services/ai.py`), so names are
   spelled right, interviewers are not mixed up with the interviewee, and
   feedback about other companies' tools goes to the context.
4. All results are stored in the database (`interviewee` and `insights` are JSON
   columns, so the sections can change without a migration); a meeting can be
   processed again, which keeps its title but writes a new summary over an
   edited one.

- The UI shows how far processing has got: uploading → upload finished →
  transcription → summary → done (or failed, with an error message).
- Interviews list (title, interviewee, date, status, View button) and interview
  details (information, "Name: key insights" with Takeaway, Context, What they
  like, What they dislike, What they want, and the transcript; empty sections are
  not shown), with loading, processing, error and empty states.
- The header of the details shows the status, the title and a pencil button
  that opens an input with "Save" and "Cancel" in place of the status and the
  title (`PATCH /api/meetings/{id}`; an empty or too long title is a 422).
- The user can edit the summary (not the transcript): "Edit summary" turns the
  whole summary into one form with one "Save" and one "Cancel". Name, role and
  location are small inputs; takeaway, context, likes, dislikes and wants are
  one text field each. In likes, dislikes and wants every item is a paragraph:
  the first line is the title, the next lines the explanation (joined into
  one line), and an empty line separates the items. The backend does the
  conversion (`app/services/summary.py`): `GET /api/meetings/{id}/summary`
  returns the form, `PUT` takes the whole edited summary, checks it with the
  same Pydantic classes as the AI summary, stores it in the same JSON columns
  and sets `edited_at`. Both answer 409 unless processing is done.
- A processed interview has a "Process again" button. It and "Try again"
  always ask for confirmation first (`ConfirmDialog`), because processing uses
  Gemini tokens; when the summary has been edited, the window also warns that
  the changes will be lost. Processing again clears `edited_at`, and the
  details show "Edited" with its date while it is set.
- A processed interview has "Copy summary" and "Copy transcript" buttons
  (`frontend/src/summaryCopy.js`, `CopyButton`). The summary is copied as it
  is shown (with the user's changes, without empty sections), both as HTML
  (bold headings, lists) for email and Slack and as plain text; the
  transcript as plain text. The button shows "Copied" for a moment, and an
  error message appears when the browser does not allow the clipboard (it
  works only on https or localhost).
- The UI texts talk about interviews; the names in the code and the API stay
  "meeting" (`Meeting`, `/api/meetings`).
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
- Write only the tests that are needed: for security (login, permissions,
  ownership), for anything whose failure would lose data or leave an interview
  stuck, and for logic that breaks easily (such as parsing). No tests for simple
  endpoints, UI texts or what an existing test already covers. When a change breaks
  an existing test, update that test. `pytest` must pass at the end of every issue.
  Tests never call Gemini or ffmpeg: they use the mocks from
  `backend/tests/conftest.py`.
- Never run commands that create, change or delete Google Cloud resources unless
  explicitly asked.
- Never commit or push unless explicitly asked.
- Write explanations in Serbian (Latin script); code, comments, commit messages and
  documentation in English.