import logging

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import ActionItem, Meeting, MeetingStatus, utc_now
from app.services.ai import AIServiceError, analyze_transcript, transcribe_audio
from app.services.audio import AudioExtractionError, extract_audio

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


def reset_results(meeting: Meeting) -> None:
    """Clear everything a previous run of the processing left on the meeting.

    The caller commits.
    """
    meeting.title = None
    meeting.transcript = None
    meeting.summary = None
    meeting.key_topics = None
    meeting.error_message = None
    meeting.processed_at = None
    # delete-orphan on the relationship: an item removed from the list is
    # deleted from the database at the next commit
    meeting.action_items.clear()


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


def process_meeting(meeting_id: int) -> None:
    """Extract the audio, transcribe it and analyze the transcript.

    Runs as a background task, after the response has been sent. The session
    of the request is closed by then, so this function gets only the id and
    opens a session of its own. It never raises: every error ends up as the
    failed status and an error message on the meeting.
    """
    with SessionLocal() as db:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None:
            logger.warning("Meeting %s does not exist, nothing to process", meeting_id)
            return

        video_path = settings.upload_path / meeting.file_path
        audio_path = video_path.with_name(AUDIO_FILENAME)
        try:
            # Every status is committed at once, so the frontend sees it while
            # the slow step that follows is still running. The commit also
            # gives the connection back to the pool for that time.
            meeting.status = MeetingStatus.TRANSCRIBING
            db.commit()

            extract_audio(video_path, audio_path)
            transcript = transcribe_audio(audio_path)

            # The transcript is saved together with the new status, so it is
            # kept even if the analysis fails
            meeting.transcript = transcript
            meeting.status = MeetingStatus.SUMMARIZING
            db.commit()

            analysis = analyze_transcript(transcript)

            meeting.title = analysis.title
            meeting.summary = analysis.summary
            meeting.key_topics = analysis.key_topics
            meeting.action_items = [
                ActionItem(assignee=item.assignee, description=item.description)
                for item in analysis.action_items
            ]
            meeting.status = MeetingStatus.DONE
            meeting.processed_at = utc_now()
            db.commit()
        except (AudioExtractionError, AIServiceError) as error:
            # The messages of these two errors are written for the user
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
