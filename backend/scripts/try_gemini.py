"""Try the Gemini API on one short MP3, outside of the application.

Run it from the backend/ folder, with the virtual environment activated:

    python -m scripts.try_gemini uploads/4/audio.mp3

It uploads the audio, asks for a transcript, then asks for a summary, key
topics and action items as JSON, and prints everything to the terminal.
"""

import sys
import time
from pathlib import Path

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.config import settings

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
    "the person speaking. Write a concise summary (2 to 4 sentences), list the "
    "key topics, and list the action items. "
    "The person responsible for an action item is the one who takes it on "
    "('I will ...', 'I can ...') or the one it is given to. "
    "As the assignee give that person's real name, when the name is said "
    "anywhere in the transcript. Use null when the name is not known or when "
    "nobody takes the task on; never use a label such as 'Speaker 1' as the "
    "assignee. In the summary, refer to people by name or role, not by such "
    "labels. "
    "Use only what is said in the transcript and do not invent anything. "
    "Write in the language of the transcript.\n\n"
    "Transcript:\n"
)

# The uploaded file is usually ready at once; wait a little if it is not
FILE_READY_TIMEOUT_SECONDS = 60
FILE_POLL_SECONDS = 2


# The shape of the JSON that the second call must return. The field names match
# the columns in app/models.py
class ActionItem(BaseModel):
    # A real name said in the meeting; None when the meeting does not say who
    # is responsible or the person's name is not known
    assignee: str | None
    description: str


class MeetingAnalysis(BaseModel):
    summary: str
    key_topics: list[str]
    action_items: list[ActionItem]


def print_usage(label: str, response: types.GenerateContentResponse, seconds: float) -> None:
    usage = response.usage_metadata
    tokens = (
        f"{usage.prompt_token_count} in, {usage.candidates_token_count} out, "
        f"{usage.total_token_count} total"
        if usage
        else "unknown"
    )
    print(f"[{label}] {seconds:.1f} s, tokens: {tokens}")


def wait_until_active(client: genai.Client, file: types.File) -> types.File:
    """Return the file once Google has finished processing it."""
    deadline = time.monotonic() + FILE_READY_TIMEOUT_SECONDS
    while file.state == types.FileState.PROCESSING:
        if time.monotonic() > deadline:
            raise RuntimeError("The uploaded file was not ready in time")
        time.sleep(FILE_POLL_SECONDS)
        file = client.files.get(name=file.name)
    if file.state == types.FileState.FAILED:
        raise RuntimeError("Google could not process the uploaded file")
    return file


def transcribe(client: genai.Client, audio_path: Path) -> str:
    started = time.perf_counter()
    audio_file = client.files.upload(file=audio_path)
    print(f"[upload] {time.perf_counter() - started:.1f} s, file: {audio_file.name}")
    try:
        audio_file = wait_until_active(client, audio_file)
        started = time.perf_counter()
        # contents is a list of parts sent together: the instruction and the audio
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[TRANSCRIBE_PROMPT, audio_file],
        )
        print_usage("transcription", response, time.perf_counter() - started)
    finally:
        # The file is only needed for this one call, so it is removed from
        # Google's storage right away instead of after the default 48 hours
        client.files.delete(name=audio_file.name)

    if not response.text:
        raise RuntimeError("The model returned an empty transcript")
    return response.text.strip()


def analyze(client: genai.Client, transcript: str) -> MeetingAnalysis:
    started = time.perf_counter()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=ANALYZE_PROMPT + transcript,
        # The model must answer with JSON that fits the MeetingAnalysis schema
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MeetingAnalysis,
        ),
    )
    print_usage("analysis", response, time.perf_counter() - started)

    # parsed is the JSON already turned into a MeetingAnalysis object; it is
    # None when the answer does not fit the schema
    if not isinstance(response.parsed, MeetingAnalysis):
        raise RuntimeError(f"The model did not return the expected JSON: {response.text}")
    return response.parsed


def main() -> int:
    # The Windows terminal does not use UTF-8 by default, and the transcript
    # may hold letters it cannot print
    sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) != 2:
        print("Usage: python -m scripts.try_gemini <path to an MP3 file>")
        return 1
    audio_path = Path(sys.argv[1])
    if not audio_path.is_file():
        print(f"File not found: {audio_path}")
        return 1

    print(f"SDK: google-genai {genai.__version__}, model: {settings.gemini_model}")
    client = genai.Client(api_key=settings.gemini_api_key)

    try:
        transcript = transcribe(client, audio_path)
        print("\n=== Transcript ===")
        print(transcript)

        analysis = analyze(client, transcript)
    except errors.APIError as error:
        # Wrong key, unknown model, quota used up, a problem on Google's side
        print(f"Gemini API error {error.code}: {error.message}")
        return 1
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1

    print("\n=== Summary ===")
    print(analysis.summary)
    print("\n=== Key topics ===")
    for topic in analysis.key_topics:
        print(f"- {topic}")
    print("\n=== Action items ===")
    if not analysis.action_items:
        print("(none)")
    for item in analysis.action_items:
        print(f"- {item.assignee or 'Unassigned'}: {item.description}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
