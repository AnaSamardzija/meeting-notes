"""Who can reach the interviews: nobody without logging in, a user only their
own, the admin all of them."""

import re

import pytest

from app.main import app
from app.models import MeetingStatus, UserRole

# The only endpoints that can be used without logging in. Every other
# endpoint, also one added later, must answer 401 without the login cookie.
PUBLIC_ENDPOINTS = {
    ("GET", "/api/health"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
}


def _all_endpoints() -> list[tuple[str, str]]:
    """Every endpoint of the app as (method, path), read from the OpenAPI
    description, which exists also when the /docs page is turned off."""
    return [
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    ]


PROTECTED_ENDPOINTS = [
    endpoint for endpoint in _all_endpoints() if endpoint not in PUBLIC_ENDPOINTS
]

# The only endpoints that need a login and still work for a user who must
# change the password the admin set. Every other protected endpoint, also one
# added later, must answer 403 to such a user.
PASSWORD_CHANGE_ENDPOINTS = {
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/password"),
}

BLOCKED_UNTIL_PASSWORD_CHANGE = [
    endpoint
    for endpoint in PROTECTED_ENDPOINTS
    if endpoint not in PASSWORD_CHANGE_ENDPOINTS
]


def test_the_meetings_endpoints_are_among_the_protected_ones():
    # Makes sure the tests below really have endpoints to check
    assert ("GET", "/api/meetings") in PROTECTED_ENDPOINTS
    assert ("POST", "/api/meetings/{meeting_id}/process") in PROTECTED_ENDPOINTS
    assert ("GET", "/api/meetings") in BLOCKED_UNTIL_PASSWORD_CHANGE
    assert ("GET", "/api/admin/users") in BLOCKED_UNTIL_PASSWORD_CHANGE


@pytest.mark.parametrize(
    "method, path", PROTECTED_ENDPOINTS, ids=[" ".join(e) for e in PROTECTED_ENDPOINTS]
)
def test_every_endpoint_except_the_public_ones_needs_a_login(
    anonymous_client, make_meeting, process_meeting_mock, method, path
):
    meeting = make_meeting()
    # {meeting_id} (or any other path parameter) becomes the id of a meeting
    # that exists, so the answer cannot be 404 instead of 401
    url = re.sub(r"\{[^}]+\}", str(meeting.id), path)

    response = anonymous_client.request(method, url)

    assert response.status_code == 401
    process_meeting_mock.assert_not_called()


@pytest.mark.parametrize(
    "method, path",
    BLOCKED_UNTIL_PASSWORD_CHANGE,
    ids=[" ".join(e) for e in BLOCKED_UNTIL_PASSWORD_CHANGE],
)
def test_a_user_with_a_temporary_password_gets_403_everywhere_else(
    client_for, db, make_user, make_meeting, process_meeting_mock, method, path
):
    # An admin, so an admin endpoint could not answer 403 for being one
    user = make_user(
        email="temporary@example.com",
        role=UserRole.ADMIN,
        must_change_password=True,
    )
    meeting = make_meeting(user_id=user.id, title=TITLE)
    url = re.sub(r"\{[^}]+\}", str(meeting.id), path)

    # A body the meeting endpoints would accept, so the answer would be a
    # success, not a 422, if the endpoint let the user in
    response = client_for(user).request(method, url, json={"title": "Changed"})

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You must change your password before continuing"
    )
    db.refresh(meeting)
    assert meeting.title == TITLE
    process_meeting_mock.assert_not_called()


# Made-up data of the meeting that belongs to another user
TITLE = "Youth coach on planning training sessions"
INTERVIEWEE = {"name": "Alex", "role": "U15 coach", "location": "Springfield"}
INSIGHTS = {
    "takeaway": "The app fits Alex well.",
    "context": "Alex coaches a U15 team.",
    "likes": [],
    "dislikes": [],
    "wants": [],
}
SUMMARY_FORM = {
    "name": "Someone else",
    "role": "",
    "location": "",
    "takeaway": "Changed by another user.",
    "context": "",
    "likes": "",
    "dislikes": "",
    "wants": "",
}


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("GET", "/api/meetings/{id}", None),
        ("PATCH", "/api/meetings/{id}", {"title": "Taken over"}),
        ("GET", "/api/meetings/{id}/summary", None),
        ("PUT", "/api/meetings/{id}/summary", SUMMARY_FORM),
        ("POST", "/api/meetings/{id}/process", None),
    ],
    ids=["details", "title", "summary form", "edit summary", "process again"],
)
def test_the_meeting_of_another_user_looks_like_one_that_does_not_exist(
    client, db, make_meeting, make_user, process_meeting_mock, method, path, body
):
    other_user = make_user(email="other@example.com")
    meeting = make_meeting(
        user_id=other_user.id,
        title=TITLE,
        transcript="Speaker 1: How do you plan your sessions?",
        interviewee=INTERVIEWEE,
        insights=INSIGHTS,
    )

    response = client.request(method, path.format(id=meeting.id), json=body)
    missing = client.request(method, path.format(id=999999), json=body)

    # The same answer as for a meeting that does not exist, so the user
    # cannot find out that it is there
    assert response.status_code == 404
    assert (response.status_code, response.json()) == (
        missing.status_code,
        missing.json(),
    )
    # Nothing was changed, and the processing was not started
    db.refresh(meeting)
    assert meeting.status == MeetingStatus.DONE
    assert meeting.title == TITLE
    assert meeting.interviewee == INTERVIEWEE
    assert meeting.insights == INSIGHTS
    assert meeting.edited_at is None
    process_meeting_mock.assert_not_called()


def test_the_list_shows_a_user_only_their_own_meetings(
    client, make_meeting, make_user
):
    other_user = make_user(email="other@example.com")
    own = make_meeting()
    make_meeting(user_id=other_user.id)

    response = client.get("/api/meetings")

    assert [row["id"] for row in response.json()] == [own.id]


def test_the_admin_sees_and_opens_the_meetings_of_every_user(
    client_for, make_meeting, make_user
):
    admin = make_user(email="admin@example.com", role=UserRole.ADMIN)
    # Owned by owner, a regular user
    meeting = make_meeting()
    admin_client = client_for(admin)

    listed = admin_client.get("/api/meetings")
    details = admin_client.get(f"/api/meetings/{meeting.id}")

    assert [row["id"] for row in listed.json()] == [meeting.id]
    assert details.status_code == 200
