from pathlib import Path
from typing import BinaryIO

# Video formats the API accepts (ffmpeg reads all of them)
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}

# How much of the file is held in memory at a time while copying
CHUNK_SIZE = 1024 * 1024  # 1 MB


class FileTooLargeError(Exception):
    """The uploaded file is larger than the allowed size."""


def save_upload(source: BinaryIO, destination: Path, max_bytes: int) -> int:
    """Copy source to destination in chunks and return the number of bytes written.

    Raises FileTooLargeError as soon as more than max_bytes have been read.
    The partial file is left on disk; the caller removes it.
    """
    written = 0
    with destination.open("wb") as target:
        while chunk := source.read(CHUNK_SIZE):
            written += len(chunk)
            if written > max_bytes:
                raise FileTooLargeError
            target.write(chunk)
    return written
