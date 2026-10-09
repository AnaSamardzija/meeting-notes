# AI notes

A short note on how AI was used in this project. The detailed journal of the
experiments with the AI provider is in [AI_EXPERIMENTS.md](AI_EXPERIMENTS.md).

## Tools used

- **Claude Code** (Anthropic), in the terminal, as the coding assistant for the
  whole project. Its rules for this repository are in `CLAUDE.md`: work in
  small steps, explain every change, ask before adding a dependency, never read
  `.env` files and never commit.
- **Google Gemini API** (Python SDK `google-genai`), as the AI inside the
  application.

## AI provider in the application

Google Gemini, model `gemini-3.8-flash`, for both steps: the transcription and
the analysis of the transcript.

Why Gemini:

- It accepts an audio file as input, so one provider and one SDK cover both the
  transcription and the summary.
- It can return JSON that follows a given schema, so the summary, the key
  topics and the action items arrive as structured data, with no parsing of
  free text.
- An API key from Google AI Studio is enough to run the project locally.

## What was AI-generated or AI-assisted

Most of the code was written with Claude Code, one GitHub issue at a time. For
every issue I described the task, read the explanation of each change, tested
the result locally and committed it myself. Claude Code was also used to review
the finished project and to plan the cleanup that followed.

The decisions were mine: the technologies, the split into issues, the database
tables, the processing statuses and what the UI shows.
