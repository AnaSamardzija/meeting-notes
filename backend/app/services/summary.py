import re

from sqlalchemy.orm import Session

from app.models import Meeting, MeetingStatus, utc_now
from app.schemas import InsightItem, Insights, Interviewee, SummaryForm
from app.services.meetings import MeetingNotFoundError, get_meeting


class SummaryNotEditableError(Exception):
    """The meeting has no finished summary, so it cannot be edited."""

# In the summary form, the items of a section (likes, dislikes or wants) are
# written in one text field, one paragraph per item: the first line is the
# title, the next lines are the explanation, and an empty line separates the
# items. The functions below turn the items into that text and back.

# An empty line between two paragraphs: a line break, any number of spaces,
# tabs and further line breaks (the \r of Windows line endings too), and
# another line break
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def _one_line(text: str) -> str:
    """Return the text on one line, with single spaces between the words."""
    # split() with no argument splits on any run of whitespace and drops the
    # whitespace at both ends
    return " ".join(text.split())


def items_to_text(items: list[InsightItem]) -> str:
    """Write the items as the text of a form field, one paragraph per item.

    The title and the explanation are each put on one line: a line break
    inside them would otherwise read as the start of the explanation or, after
    an empty line, as a new item.
    """
    paragraphs = []
    for item in items:
        title = _one_line(item.title)
        explanation = _one_line(item.explanation)
        paragraphs.append(f"{title}\n{explanation}" if explanation else title)
    return "\n\n".join(paragraphs)


def text_to_items(text: str) -> list[InsightItem]:
    """Read the items from the text of a form field.

    Extra empty lines and spaces are ignored. The lines of the explanation are
    joined with a space, so items_to_text gives the same text back. An empty
    field gives an empty list.
    """
    items = []
    for paragraph in _PARAGRAPH_BREAK.split(text):
        lines = [_one_line(line) for line in paragraph.splitlines()]
        lines = [line for line in lines if line]
        # Empty when the text begins or ends with empty lines
        if lines:
            items.append(InsightItem(title=lines[0], explanation=" ".join(lines[1:])))
    return items


NOT_EDITABLE_MESSAGE = "The summary can be changed only when processing is done"


def get_summary_form(db: Session, meeting_id: int) -> SummaryForm:
    """Return the summary of the meeting in the shape of the form.

    Raises MeetingNotFoundError, or SummaryNotEditableError if the processing
    is not done.
    """
    meeting = get_meeting(db, meeting_id)
    if meeting.status != MeetingStatus.DONE:
        raise SummaryNotEditableError(NOT_EDITABLE_MESSAGE)

    # The JSON columns hold plain dicts; model_validate turns them back into
    # the classes they were made from
    person = Interviewee.model_validate(meeting.interviewee)
    insights = Insights.model_validate(meeting.insights)
    return SummaryForm(
        name=person.name or "",
        role=person.role or "",
        location=person.location or "",
        takeaway=insights.takeaway,
        context=insights.context,
        likes=items_to_text(insights.likes),
        dislikes=items_to_text(insights.dislikes),
        wants=items_to_text(insights.wants),
    )


def update_summary(db: Session, meeting_id: int, form: SummaryForm) -> Meeting:
    """Replace the summary of the meeting with the edited one and return the
    meeting.

    Raises MeetingNotFoundError, or SummaryNotEditableError if the processing
    is not done.
    """
    # Locked until the commit, as in start_reprocessing: the processing cannot
    # start between the check of the status and the save, so it never ends up
    # writing its summary over this one or the other way round
    meeting = db.get(Meeting, meeting_id, with_for_update=True)
    if meeting is None:
        raise MeetingNotFoundError("Meeting not found")
    if meeting.status != MeetingStatus.DONE:
        raise SummaryNotEditableError(NOT_EDITABLE_MESSAGE)

    # Built with the same classes as the summary of the AI, so the columns
    # always hold the same shape. An empty value is stored as None, as the AI
    # does it (see analyze_transcript in app/services/ai.py)
    person = Interviewee(
        name=form.name.strip() or None,
        role=form.role.strip() or None,
        location=form.location.strip() or None,
    )
    insights = Insights(
        context=form.context.strip(),
        likes=text_to_items(form.likes),
        dislikes=text_to_items(form.dislikes),
        wants=text_to_items(form.wants),
        takeaway=form.takeaway.strip(),
    )
    meeting.interviewee = person.model_dump()
    meeting.insights = insights.model_dump()
    meeting.edited_at = utc_now()
    db.commit()
    return meeting
