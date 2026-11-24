import logging

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Meeting, MeetingStatus, utc_now
from app.services.ai import AIServiceError, analyze_transcript, transcribe_audio
from app.services.audio import (
    AudioExtractionError,
    InvalidVideoError,
    check_video_length,
    extract_audio,
    get_media_duration,
)

logger = logging.getLogger(__name__)

# The temporary MP3, next to the video in the folder of the meeting
AUDIO_FILENAME = "audio.mp3"

# A meeting in one of these statuses has a background task of its own.
# uploaded counts too: the task is already scheduled, it has only not written
# its first status yet
IN_PROGRESS_STATUSES = (
    MeetingStatus.UPLOADED,
    MeetingStatus.TRANSCRIBING,
    MeetingStatus.SUMMARIZING,
)

UNEXPECTED_ERROR_MESSAGE = "An unexpected error occurred while processing the meeting"
INTERRUPTED_MESSAGE = "Processing was interrupted because the server was restarted"


def _mark_failed(db: Session, meeting: Meeting, meeting_id: int, message: str) -> None:
    """Store the failed status and the reason on the meeting.

    meeting_id is passed separately for the log: after a rollback, reading
    meeting.id asks the database again, and that fails if the database is down.
    """
    try:
        # Throw away whatever the failed step left half done in the session
        db.rollback()
        meeting.status = MeetingStatus.FAILED
        meeting.error_message = message
        db.commit()
    except SQLAlchemyError:
        # Nothing more can be done here (e.g. the database is down); the
        # meeting is marked as failed the next time the application starts
        logger.exception("Could not mark meeting %s as failed", meeting_id)


def process_meeting(meeting_id: int, transcribe: bool = True) -> None:
    """Extract the audio, transcribe it and analyze the transcript.

    With transcribe=False only the analysis runs, on the transcript the
    meeting already has: no ffmpeg and no transcription, which cost the most
    tokens. start_reprocessing (app/services/meetings.py) decides this.

    Runs as a background task, after the response has been sent. The session
    of the request is closed by then, so this function gets only the id and
    opens a session of its own. It never raises: every error ends up as the
    failed status and an error message on the meeting.

    The old results are never cleared in advance: each new result replaces the
    old one in the same commit that moves the meeting to the next status. A
    failed step is rolled back (see _mark_failed), so the meeting keeps the
    last transcript and summary that were stored.
    """
    with SessionLocal() as db:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None:
            logger.warning("Meeting %s does not exist, nothing to process", meeting_id)
            return

        video_path = settings.upload_path / meeting.file_path
        audio_path = video_path.with_name(AUDIO_FILENAME)
        try:
            if transcribe:
                # Every status is committed at once, so the frontend sees it
                # while the slow step that follows is still running. The
                # commit also gives the connection back to the pool for that
                # time.
                meeting.status = MeetingStatus.TRANSCRIBING
                db.commit()

                # The same check as at upload, before anything is sent to
                # Gemini. It matters when an older video, uploaded before the
                # limit or with a higher one, is processed again
                check_video_length(get_media_duration(video_path))

                extract_audio(video_path, audio_path)
                # The id and the length of the recording are only for the log
                # line of each Gemini call (see _log_usage in app/services/ai.py)
                audio_seconds = get_media_duration(audio_path)
                transcript = transcribe_audio(
                    audio_path, meeting_id=meeting_id, audio_seconds=audio_seconds
                )

                # The new transcript replaces the old one together with the
                # new status, so it is kept even if the analysis fails (and
                # "Try again" then needs only a new summary)
                meeting.transcript = transcript
                meeting.status = MeetingStatus.SUMMARIZING
                db.commit()
            else:
                # start_reprocessing has already set the summarizing status
                transcript = meeting.transcript

            analysis = analyze_transcript(transcript, meeting_id=meeting_id)

            # The AI title is used only when the meeting has no title. The
            # check is done by the database (WHERE title IS NULL), not with
            # meeting.title: that is the value read when the processing
            # started, and the user may have set a title since then.
            db.execute(
                update(Meeting)
                .where(Meeting.id == meeting_id, Meeting.title.is_(None))
                .values(title=analysis.title)
                # Leave the meeting object in the session as it is: it would
                # be changed from the same old value, so it could show a title
                # the database did not get. Nothing below reads it.
                .execution_options(synchronize_session=False)
            )
            # model_dump turns the Pydantic objects into plain dicts, which
            # the JSON columns can store. The new summary replaces the old one
            # only here, in the same commit as the done status
            meeting.interviewee = analysis.interviewee.model_dump()
            meeting.insights = analysis.insights.model_dump()
            # The summary is the AI's again, so it is no longer an edited one
            meeting.edited_at = None
            meeting.error_message = None
            meeting.status = MeetingStatus.DONE
            meeting.processed_at = utc_now()
            db.commit()
        except (InvalidVideoError, AudioExtractionError, AIServiceError) as error:
            # The messages of these errors are written for the user
            _mark_failed(db, meeting, meeting_id, str(error))
        except Exception:
            # Anything else is a bug or a database problem: the details go to
            # the log, the user gets a general message
            logger.exception("Processing of meeting %s failed", meeting_id)
            _mark_failed(db, meeting, meeting_id, UNEXPECTED_ERROR_MESSAGE)
        finally:
            # The MP3 is only needed for the transcription
            try:
                audio_path.unlink(missing_ok=True)
            except OSError as error:
                logger.warning("Could not delete %s: %s", audio_path, error)


def fail_interrupted_meetings() -> int:
    """Mark the meetings that were being processed when the server stopped
    as failed, and return how many there were.

    A background task lives only in the memory of the server, so after a
    restart nothing is working on these meetings any more.
    """
    with SessionLocal() as db:
        result = db.execute(
            update(Meeting)
            .where(Meeting.status.in_(IN_PROGRESS_STATUSES))
            .values(status=MeetingStatus.FAILED, error_message=INTERRUPTED_MESSAGE)
        )
        db.commit()
        return result.rowcount
