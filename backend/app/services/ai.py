import logging
import time
from pathlib import Path

import httpx
from google import genai
from google.genai import errors, types

# The errors of the Interactions API. The SDK has no public module for them
# yet, so they come from a private one; the SDK version is pinned in
# requirements.txt, and this import is the first thing to check after an upgrade
from google.genai._gaos.lib.compat_errors import (
    APIConnectionError as InteractionsConnectionError,
    APIError as InteractionsAPIError,
    APITimeoutError as InteractionsTimeoutError,
)
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

# The uploaded file is usually ready at once; wait a little if it is not
FILE_READY_TIMEOUT_SECONDS = 60
FILE_POLL_SECONDS = 2

# The title column in app/models.py is String(255)
TITLE_MAX_LENGTH = 255

# Everything the SDK raises when a call fails. The two parts of the SDK use
# different classes:
# - the Files API: errors.APIError when Google answers with an error,
#   httpx.HTTPError when no answer comes (no network, timeout)
# - the Interactions API: InteractionsAPIError for both cases
SDK_ERRORS = (errors.APIError, httpx.HTTPError, InteractionsAPIError)

TRANSCRIBE_PROMPT = (
    "Transcribe the speech in this meeting recording word for word, in the "
    "language that is spoken. Start a new line every time the speaker changes. "
    "Every line must begin with a speaker label and a colon, with no "
    "exceptions: the speaker's name if it is said in the recording, otherwise "
    "'Speaker 1', 'Speaker 2' and so on. Tell the speakers apart by their "
    "voices and keep the same label for the same voice in the whole recording. "
    "Return only the transcript, with no introduction or comments."
)

ANALYZE_PROMPT = (
    "Below is the transcript of a meeting. Every line begins with the label of "
    "the person speaking. Give the meeting a short title (at most 10 words), "
    "write a concise summary (2 to 4 sentences), list the key topics, and list "
    "the action items. "
    "The person responsible for an action item is the one who takes it on "
    "('I will ...', 'I can ...') or the one it is given to. "
    "As the assignee give that person's real name, but only when the name is "
    "actually said in the transcript. Use null when the name is not known or "
    "when nobody takes the task on; never guess a name and never use a label "
    "such as 'Speaker 1' as the assignee. In the title and the summary, refer "
    "to people by name or role, not by such labels. "
    "Use only what is said in the transcript and do not invent anything. "
    "Write the title, the summary, the key topics and the action items in the "
    "language that is spoken in the meeting, not in the language of these "
    "instructions.\n\n"
    "Transcript:\n"
)


class AIServiceError(Exception):
    """The AI call failed; the message is safe to show to the user."""


# The shape of the JSON that Gemini must return for the analysis. The field
# names match the columns in app/models.py
class ActionItemResult(BaseModel):
    # A real name said in the meeting; None when the meeting does not say who
    # is responsible or the person's name is not known
    assignee: str | None
    description: str


class MeetingAnalysis(BaseModel):
    title: str
    summary: str
    key_topics: list[str]
    action_items: list[ActionItemResult]


def _client() -> genai.Client:
    """Create a Gemini client with the key and the timeout from the settings."""
    return genai.Client(
        api_key=settings.gemini_api_key,
        # The SDK expects milliseconds
        http_options=types.HttpOptions(
            timeout=settings.gemini_timeout_seconds * 1000
        ),
    )


def _to_service_error(error: Exception) -> AIServiceError:
    """Turn an error of the SDK into an AIServiceError with a clear message.

    The user gets a short message; what the SDK said goes to the log.
    """
    logger.error("Gemini call failed: %r", error)

    # No answer came at all. A timeout is one kind of connection error in both
    # families, so it is checked first
    if isinstance(error, (httpx.TimeoutException, InteractionsTimeoutError)):
        return AIServiceError("The request to Gemini took too long and was stopped")
    if isinstance(error, (httpx.HTTPError, InteractionsConnectionError)):
        return AIServiceError("Could not connect to Gemini")

    # Google answered with an error. The HTTP status is called code in the
    # errors of the Files API and status_code in those of the Interactions API
    code = getattr(error, "code", None) or getattr(error, "status_code", None) or 0
    message = str(getattr(error, "message", "") or "")

    if code == 429:
        return AIServiceError(
            "The Gemini usage limit has been reached. Try again later."
        )
    if code == 404:
        return AIServiceError(
            f"The Gemini model '{settings.gemini_model}' was not found. "
            "Check GEMINI_MODEL."
        )
    # Google answers a wrong key with 400, not with 401
    if code in (401, 403) or (code == 400 and "api key" in message.lower()):
        return AIServiceError("The Gemini API key is not valid. Check GEMINI_API_KEY.")
    if code >= 500:
        return AIServiceError("Gemini is not available at the moment. Try again later.")
    return AIServiceError(f"Gemini rejected the request (error {code})")


def _wait_until_active(client: genai.Client, file: types.File) -> types.File:
    """Return the file once Google has finished processing it."""
    deadline = time.monotonic() + FILE_READY_TIMEOUT_SECONDS
    while file.state == types.FileState.PROCESSING:
        if time.monotonic() > deadline:
            raise AIServiceError("Gemini did not finish preparing the audio in time")
        time.sleep(FILE_POLL_SECONDS)
        file = client.files.get(name=file.name)
    if file.state == types.FileState.FAILED:
        raise AIServiceError("Gemini could not process the audio file")
    return file


def _delete_file(client: genai.Client, file: types.File) -> None:
    """Remove the uploaded file from Google's storage.

    A failure is only logged: it must not hide the real error or throw away a
    transcript that was already made. Google deletes the file itself after 48
    hours anyway.
    """
    try:
        client.files.delete(name=file.name)
    except SDK_ERRORS as error:
        logger.warning("Could not delete the Gemini file %s: %s", file.name, error)


def transcribe_audio(audio_path: Path) -> str:
    """Return the transcript of the speech in the MP3 file at audio_path.

    Raises AIServiceError if the file is missing or Gemini cannot transcribe it.
    """
    if not audio_path.is_file():
        raise AIServiceError("The audio file was not found")

    client = _client()
    # The audio goes to Google's Files API first, and the request then only
    # points to it. Sending the bytes inside the request works for small files
    # only (the whole request may not be larger than 20 MB)
    try:
        audio_file = client.files.upload(file=audio_path)
        try:
            audio_file = _wait_until_active(client, audio_file)
            # input is a list of parts sent together: the instruction and the
            # audio, which is given by the address of the uploaded file
            interaction = client.interactions.create(
                model=settings.gemini_model,
                input=[
                    {"type": "text", "text": TRANSCRIBE_PROMPT},
                    {
                        "type": "audio",
                        "uri": audio_file.uri,
                        "mime_type": audio_file.mime_type,
                    },
                ],
                # Google keeps every interaction for days by default; nothing
                # here needs that, and a meeting is private
                store=False,
            )
        finally:
            # The file is only needed for this one call, so it is removed
            # right away, whether the call worked or not
            _delete_file(client, audio_file)
    except SDK_ERRORS as error:
        # from None: the user-facing error replaces the SDK one, which is
        # already in the log
        raise _to_service_error(error) from None

    # Any other status (e.g. "incomplete", "failed") means there is no full answer
    if interaction.status != "completed":
        logger.error("Gemini transcription ended as %s", interaction.status)
        raise AIServiceError("Gemini did not finish the transcription")

    # output_text is only the final answer of the model, without its thinking
    # steps; it is empty when the model returned no text at all
    transcript = (interaction.output_text or "").strip()
    # A safety net: with the older generateContent API the model now and then
    # wrote the word "thought" on a line of its own before the transcript. A
    # real line always begins with a speaker label and a colon, so such a
    # first line is never part of the meeting
    first_line, _, rest = transcript.partition("\n")
    if first_line.strip() == "thought":
        transcript = rest.strip()
    if not transcript:
        raise AIServiceError("Gemini returned an empty transcript")
    return transcript


def analyze_transcript(transcript: str) -> MeetingAnalysis:
    """Return the title, summary, key topics and action items of a meeting.

    Raises AIServiceError if the transcript is empty or Gemini does not return
    an answer in the expected shape.
    """
    if not transcript.strip():
        raise AIServiceError("The transcript is empty")

    # Kept in a variable on purpose: a client that nothing refers to any more
    # is closed by Python, even in the middle of a call
    client = _client()
    try:
        interaction = client.interactions.create(
            model=settings.gemini_model,
            input=ANALYZE_PROMPT + transcript,
            # The model must answer with JSON that fits the MeetingAnalysis
            # schema; model_json_schema() is that class written as a JSON schema
            response_format=[
                {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": MeetingAnalysis.model_json_schema(),
                }
            ],
            # See transcribe_audio: nothing is kept on Google's side
            store=False,
        )
    except SDK_ERRORS as error:
        raise _to_service_error(error) from None

    if interaction.status != "completed":
        logger.error("Gemini analysis ended as %s", interaction.status)
        raise AIServiceError("Gemini did not finish the analysis")

    # The answer is JSON as text. model_validate_json turns it into a
    # MeetingAnalysis object and checks it against the class at the same time
    try:
        analysis = MeetingAnalysis.model_validate_json(interaction.output_text or "")
    except ValidationError:
        logger.error(
            "Gemini returned an unexpected analysis: %s", interaction.output_text
        )
        raise AIServiceError(
            "Gemini returned an answer in an unexpected format"
        ) from None

    # The schema only checks the types, so tidy up the values themselves
    analysis.title = analysis.title.strip()[:TITLE_MAX_LENGTH]
    analysis.summary = analysis.summary.strip()
    analysis.key_topics = [topic.strip() for topic in analysis.key_topics]
    for item in analysis.action_items:
        item.description = item.description.strip()
        # "" or spaces instead of null still means that nobody is named
        item.assignee = (item.assignee or "").strip() or None
    return analysis
