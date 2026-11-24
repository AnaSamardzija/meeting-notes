# Meeting Notes AI

The app started as a take-home assignment and is now being prepared for production
as an internal company tool for user interviews with players and coaches (product
feedback), used mainly by one colleague. Work is split into GitHub issues, one
branch per issue. Where an issue conflicts with what this file
says about the app, the issue wins and this file is updated as part of the issue.

## What the app does now
A small web app with user accounts (see "Users and login" below):
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
   processed again (see "Process again" below), which keeps its title but
   writes a new summary over an edited one once the new summary is ready.

- Limits of an upload: `MAX_UPLOAD_MB` (default 500) and `MAX_VIDEO_MINUTES`
  (default 120, because Gemini charges for every second of audio). The upload
  reads the length of the saved video with ffprobe (`get_media_duration` and
  `check_video_length` in `app/services/audio.py`): a longer video, or one
  whose length cannot be read, is a 422 with a message for the user (e.g.
  "The video is 2 h 14 min long; the longest allowed is 2 hours."), which the
  upload form shows, and neither the file nor the row is kept. The processing
  does the same check before ffmpeg and Gemini, so transcribing an older,
  longer video again ends as failed with the same message.
  `UploadSizeLimitMiddleware` (`app/upload_limit.py`, added before the CORS
  middleware so its answers have the CORS headers) checks the
  `Content-Length` of `POST /api/meetings` before the body is read, so also
  before the login: larger than `MAX_UPLOAD_MB` plus 1 MB for the other form
  fields is a 413, no `Content-Length` a 411. In production it is replaced by
  uploading straight to Cloud Storage.
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
  the changes will be lost once the new summary is ready.
  `POST /api/meetings/{id}/process` takes an optional body
  `{"transcribe": true}`. An interview with a transcript gets by default only
  a new summary from it (no ffmpeg, no transcription; `start_reprocessing`
  sets `summarizing` at once); one without a transcript, or with
  `transcribe` true, is processed from the audio (`transcribing`). A new
  transcript is never made without a new summary. Nothing is cleared in
  advance: the new transcript replaces the old one in the commit that moves
  the interview to `summarizing`, and the new summary replaces the old one
  (and `edited_at` is cleared) in the commit that moves it to `done`. A failed
  processing leaves the last stored transcript and summary, which the details
  show under the error message; meanwhile the details show the old summary,
  which cannot be edited (409). For an interview with a transcript the window
  offers "New summary only" (selected) and "New transcript and summary";
  without one there is no choice. The details show "Edited" with its date
  while `edited_at` is set.
- A processed interview has "Copy summary" and "Copy transcript" buttons
  (`frontend/src/summaryCopy.js`, `CopyButton`). The summary is copied as it
  is shown (with the user's changes, without empty sections), both as HTML
  (bold headings, lists) for email and Slack and as plain text; the
  transcript as plain text. The button shows "Copied" for a moment, and an
  error message appears when the browser does not allow the clipboard (it
  works only on https or localhost).
- After every Gemini call whose answer came back (also a failed one, and on
  every processing again), `_log_usage` in `app/services/ai.py` writes one
  INFO log line: meeting id, step (`transcription` or `analysis`), model,
  status, duration of the call in seconds, input, output and thought tokens
  (from `usage` of the Interactions API) and, for the transcription, the
  length of the MP3 in seconds (`get_media_duration`, ffprobe). The numbers
  are in the text and as separate fields of the record (`extra`). No content
  of the interview goes to the log, no price is computed (the exact cost is in
  the billing of the Google Cloud project), and nothing is stored in the
  database; a table is added only if the numbers are ever needed in the app.
- Users and login. Table `users`: email (unique,
  stored in lower case), argon2 password hash only (`argon2-cffi`), role
  `user` or `admin`, `is_active`, `token_version`, `must_change_password`,
  `created_at`.
  `POST /api/auth/register`
  (open for now; always role `user`; 409 for a taken email, 422 for a password
  under 10 characters or, when `ALLOWED_EMAIL_DOMAIN` is set, another domain),
  `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`,
  `POST /api/auth/password` (current and new password; 400 for a wrong current
  password and for a new password equal to the current one, never 401, which
  the frontend treats as a lost login; sets `must_change_password` to false).
  The user (`UserRead`, from `/me`, login, register and the admin list)
  includes `must_change_password`.
  Register and login put a JWT (`PyJWT`, HS256, `JWT_SECRET`; claims `sub`,
  `ver` = the user's `token_version`, `iat`, `exp`) in the httpOnly,
  Secure, SameSite=Strict cookie `access_token`, valid `JWT_EXPIRE_HOURS`
  (default 168 = 7 days) from the login, not extended while the user works.
  Logout only deletes the cookie. A password change increases
  `token_version`, so every older token (other browsers) stops working; the
  browser that changed it gets a new cookie and stays logged in.
  Unknown email, wrong password and deactivated account all get the same 401.
  `get_current_user` (reads the cookie, checks the JWT, loads the user; 401
  also for a deactivated user and for a token whose `ver` is not the user's
  `token_version`; then 403 "You must change your password before
  continuing" while `must_change_password` is true) and `require_admin` (403)
  are in `app/dependencies.py`. Only `/me` and `/password` use
  `get_current_user_allow_temporary_password` (the same without the 403), so
  a user with a temporary password can reach only them (and the public
  endpoints). The admin is made only by `python -m app.create_admin`
  from `ADMIN_EMAIL` and `ADMIN_PASSWORD`: it can run any number of times,
  changes nothing when the admin exists, and never makes an existing regular
  user an admin. Email confirmation and a "forgot password" flow are not
  done; the admin sets a new password instead (see below).
- User management, admin only (`app/routers/admin.py`, router with
  `dependencies=[Depends(require_admin)]`, so 401 without a login and 403 for
  everyone else; logic in `app/services/users.py`):
  `GET /api/admin/users` (every user, deactivated ones too, by email),
  `PATCH /api/admin/users/{id}` with `{"is_active": bool}` (returns the user)
  and `POST /api/admin/users/{id}/password` with `{"new_password"}` (same
  rules as at registration; 204). Unknown user 404. The admin cannot
  deactivate themselves or set their own password this way (400; their own
  password is changed on `/profile`). Users are never deleted, only
  deactivated, and their interviews stay. Deactivating and setting a password
  both increase `token_version`, so every older cookie of the user stops
  working, also after the account is activated again. Setting a password also
  sets `must_change_password`: the user must change the password (which the
  admin knows) before doing anything else.
- Frontend pages (`react-router`, declarative mode; `frontend/src/App.jsx`,
  page components in `frontend/src/pages/`): `/login`, `/register`, `/` (the
  interviews list), `/meetings/:id` (the details) and `/profile` (email, role,
  date the account was created, and a password change form with current, new
  and confirmed new password) and `/admin/users` (admin only: email, role,
  status, date created; "Deactivate" with a `ConfirmDialog`, "Activate", and
  "Set password" with a form under the row; no buttons on the admin's own
  row), so a refresh and a link
  to an interview work; any other address goes to `/`. `RequireAuth` sends a
  user who is not logged in to `/login` and a user with
  `must_change_password` from any other page to `/profile` (which then shows
  a warning above the password form), `RequireAdmin` (inside
  `RequireAuth`) sends anyone who is not an admin to `/`, `GuestOnly` sends a logged-in user
  from `/login` and `/register` to `/` (also right after a login). The login
  page has email, password, an error message and a link to registration; the
  register page has email, password, password confirmation (compared only in
  the frontend), an error message and a link to the login, and logs the user
  in at once. `AuthProvider` (`authContext.js`, `useAuth()`) holds the user:
  it asks `GET /api/auth/me` at startup and after every login and
  registration (a 401 there means the browser did not keep the cookie:
  `LoginCookieError`), and after a password change (its `changePassword`).
  The navigation shows "Users" (a link to `/admin/users`, only for the admin
  and not while the password must be changed), the user's email (a link to
  `/profile`) and "Logout".
  axios sends the cookie with every request (`withCredentials`), and its
  interceptor in `api.js` turns any 401 (except a failed login) into a logout
  in the UI, which leads to `/login`.
- CORS allows credentials (`allow_credentials=True`) only for the exact
  addresses in `CORS_ORIGINS`; `config.py` refuses `*` and empty entries, so
  the backend does not start with them.
- Interviews belong to users. All `/api/meetings` endpoints need a login (the
  router has `dependencies=[Depends(get_current_user)]`; 401 without a valid
  cookie). `meetings.user_id` (foreign key to `users`) is set at upload to the
  user who uploaded. A user sees, edits and processes again only their own
  interviews, the admin all of them: every service function that works on
  one interview gets it through `get_meeting(db, meeting_id, user)` in
  `app/services/meetings.py`, which filters in the SQL query, so another
  user's interview is a 404 exactly like one that does not exist. The
  migration that added `user_id` gave the existing interviews to the admin
  and stops when there are interviews but no admin yet. Every row of
  `GET /api/meetings` has `owner_email` (the uploader); the list shows it in
  an "Owner" column only to the admin.
- On a screen narrower than 992px the interviews list and the users table
  show every row as a card (`.table-stack` in `frontend/src/index.css`, with
  `data-label` on the cells), so the page does not scroll sideways.
- Swagger (`/docs`, `/redoc`, `/openapi.json`) exists only when
  `ENABLE_DOCS=true`; it is off by default and in production.
- The UI texts talk about interviews; the names in the code and the API stay
  "meeting" (`Meeting`, `/api/meetings`).
- Errors are returned with proper HTTP status codes; API keys and the JWT
  secret come only from environment variables.

## Approach
- AI provider: Google Gemini (Python SDK `google-genai`).
- Database: MySQL in Docker (`docker-compose.yml` with only the `db` service for now).
- Frontend: React + Vite, JavaScript (not TypeScript).
- Processing is slow, so the upload returns immediately, processing runs in the
  background, the status is stored in the database and the frontend polls for it.

## Project structure
- backend/ – FastAPI app, Python virtual environment in backend/.venv
- backend/tests/ – pytest tests; shared fixtures in backend/tests/conftest.py
- frontend/ – React + Vite (JavaScript); pages in frontend/src/pages/, other
  components in frontend/src/components/

## Commands
- Backend: `cd backend`, then `fastapi dev app/main.py` (http://localhost:8000/docs
  with `ENABLE_DOCS=true`)
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
- Every new endpoint needs a login (`get_current_user`); only health, register,
  login and logout are public (`PUBLIC_ENDPOINTS` in
  `backend/tests/test_meeting_access.py`, whose test fails for any other
  endpoint that answers without a login). A new endpoint uses
  `get_current_user`, never `get_current_user_allow_temporary_password`, so a
  user with a temporary password gets 403 there (`PASSWORD_CHANGE_ENDPOINTS`
  in the same test file lists the only exceptions, `/me` and `/password`).
  An endpoint for an interview checks
  ownership by getting it through `get_meeting(db, meeting_id, user)`: another
  user's interview is a 404, never a 403. An endpoint only for the admin goes
  under `/api/admin/` (`app/routers/admin.py` or another router with
  `require_admin`); `backend/tests/test_admin.py` checks that every one of
  them answers 403 to a regular user.
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