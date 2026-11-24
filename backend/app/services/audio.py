import logging
import math
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Enough for speech, and it keeps the MP3 small (about 0.5 MB per minute)
AUDIO_CHANNELS = "1"  # mono
AUDIO_SAMPLE_RATE = "16000"  # 16 kHz
AUDIO_BITRATE = "64k"  # 64 kbit/s

# ffprobe only reads the start of the file, so it finishes in about a second.
# The limit for ffmpeg itself comes from FFMPEG_TIMEOUT_SECONDS in .env
PROBE_TIMEOUT_SECONDS = 30

INVALID_VIDEO_MESSAGE = "The video file is corrupted or is not a valid video"


class AudioExtractionError(Exception):
    """The audio could not be extracted; the message is safe to show to the user."""


class InvalidVideoError(Exception):
    """The video is too long or its length cannot be read; the message is safe
    to show to the user."""


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    """Run ffmpeg or ffprobe and return its exit code and output.

    The command is a list, so it is started directly, without a shell: a file
    name with spaces or special characters is always just one argument.
    """
    try:
        # errors="replace": the output may hold bytes that are not valid UTF-8
        # (e.g. a file name), and that must not crash the call
        return subprocess.run(
            command,
            # check=False: a failed run does not raise; the callers read the
            # exit code themselves and write their own message
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        # Raised by Python when the program itself (command[0]) does not exist
        # from None: the original error is replaced on purpose, so the traceback
        # does not show it as a second error
        raise AudioExtractionError(
            "ffmpeg is not installed or is not on the PATH"
        ) from None
    except subprocess.TimeoutExpired:
        # subprocess.run has already stopped the program at this point
        raise AudioExtractionError(
            "Extracting the audio took too long and was stopped"
        ) from None


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Create a mono 16 kHz 64 kbit/s MP3 at audio_path from the video.

    Raises AudioExtractionError if ffmpeg is missing, the file is not a
    readable video, it has no audio track or the conversion takes too long.
    """
    if not video_path.is_file():
        raise AudioExtractionError("The video file was not found")
    if not audio_path.parent.is_dir():
        raise AudioExtractionError("The folder for the audio file does not exist")

    # ffprobe only reads the file: print the index of every audio stream,
    # one per line
    probe = _run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(video_path),
        ],
        PROBE_TIMEOUT_SECONDS,
    )
    if probe.returncode != 0:
        logger.error("ffprobe failed for %s: %s", video_path, probe.stderr.strip())
        raise AudioExtractionError(INVALID_VIDEO_MESSAGE)
    if not probe.stdout.strip():
        raise AudioExtractionError("The video has no audio track")

    try:
        result = _run(
            [
                "ffmpeg",
                "-nostdin",  # never wait for keyboard input
                "-hide_banner",
                "-loglevel", "error",
                "-y",  # overwrite the output file if it exists
                "-i", str(video_path),
                "-vn",  # no video in the output
                "-ac", AUDIO_CHANNELS,
                "-ar", AUDIO_SAMPLE_RATE,
                "-b:a", AUDIO_BITRATE,
                "-f", "mp3",  # always MP3, whatever the extension of audio_path
                str(audio_path),
            ],
            settings.ffmpeg_timeout_seconds,
        )
    except AudioExtractionError:
        # a run that was stopped half way leaves a partial file behind
        audio_path.unlink(missing_ok=True)
        raise
    if result.returncode != 0:
        # The user gets a short message; the reason ffmpeg gave goes to the log
        logger.error("ffmpeg failed for %s: %s", video_path, result.stderr.strip())
        # ffmpeg may leave a partial file behind
        audio_path.unlink(missing_ok=True)
        raise AudioExtractionError("Could not extract audio from the video")


def get_media_duration(path: Path) -> float | None:
    """Return the length of a video or audio file in seconds, or None if it is
    not known.

    This never raises: each caller decides what an unknown length means. The
    length of the video is checked with check_video_length; the length of the
    MP3 only goes to the log (see app/services/ai.py).
    """
    try:
        # Print only the duration of the whole file, as a bare number
        probe = _run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(path),
            ],
            PROBE_TIMEOUT_SECONDS,
        )
    except AudioExtractionError as error:
        logger.warning("Could not read the length of %s: %s", path, error)
        return None
    if probe.returncode != 0:
        logger.warning("ffprobe failed for %s: %s", path, probe.stderr.strip())
        return None
    # ffprobe prints "N/A" when it cannot tell the length
    try:
        return round(float(probe.stdout.strip()), 1)
    except ValueError:
        logger.warning("ffprobe returned no length for %s", path)
        return None


def _format_minutes(minutes: int) -> str:
    """Write a number of minutes for the user: "2 hours", "1 hour", "45 min"
    or "2 h 14 min"."""
    # divmod returns the whole hours and the minutes that are left
    hours, rest = divmod(minutes, 60)
    if rest == 0:
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    if hours == 0:
        return f"{rest} min"
    return f"{hours} h {rest} min"


def check_video_length(seconds: float | None) -> None:
    """Raise InvalidVideoError if the video is longer than MAX_VIDEO_MINUTES,
    or if its length is not known (seconds is None).

    It gets the length, not the file, so it runs without ffprobe: the caller
    reads the length with get_media_duration.
    """
    if seconds is None:
        # ffprobe could not read the file, so it is not a video ffmpeg can use
        raise InvalidVideoError(INVALID_VIDEO_MESSAGE)
    limit = settings.max_video_minutes
    if seconds > limit * 60:
        # Rounded up, so a video a few seconds over the limit is never shown
        # as exactly as long as the limit
        length = _format_minutes(math.ceil(seconds / 60))
        raise InvalidVideoError(
            f"The video is {length} long; "
            f"the longest allowed is {_format_minutes(limit)}."
        )
