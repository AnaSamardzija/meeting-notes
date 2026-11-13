"""Try the AI service on one short MP3, outside of the application.

Run it from the backend/ folder, with the virtual environment activated:

    python -m scripts.try_gemini uploads/4/audio.mp3

It calls the two functions of app/services/ai.py, the same ones the
application uses, and prints the transcript, the title, the interviewee and
the insights to the terminal.
"""

import sys
import time
from pathlib import Path

from app.config import settings
from app.schemas import InsightItem
from app.services.ai import AIServiceError, analyze_transcript, transcribe_audio


def print_items(heading: str, items: list[InsightItem]) -> None:
    print(f"\n=== {heading} ===")
    if not items:
        print("(none)")
    for item in items:
        print(f"- {item.title}: {item.explanation}")


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

    print(f"Model: {settings.gemini_model}")

    try:
        started = time.perf_counter()
        transcript = transcribe_audio(audio_path)
        print(f"[transcription] {time.perf_counter() - started:.1f} s")
        print("\n=== Transcript ===")
        print(transcript)

        started = time.perf_counter()
        analysis = analyze_transcript(transcript)
        print(f"\n[analysis] {time.perf_counter() - started:.1f} s")
    except AIServiceError as error:
        # The service has already turned every SDK error into a clear message
        print(f"Error: {error}")
        return 1

    person = analysis.interviewee
    insights = analysis.insights
    print("\n=== Title ===")
    print(analysis.title)
    print("\n=== Interviewee ===")
    print(f"Name: {person.name or '(unknown)'}")
    print(f"Role: {person.role or '(unknown)'}")
    print(f"Location: {person.location or '(unknown)'}")
    print("\n=== Takeaway ===")
    print(insights.takeaway)
    print("\n=== Context ===")
    print(insights.context)
    print_items("What they like", insights.likes)
    print_items("What they dislike", insights.dislikes)
    print_items("What they want", insights.wants)
    return 0


if __name__ == "__main__":
    sys.exit(main())
