"""Tests of the user management of the admin: only the admin can use it, the
admin cannot lock themselves out, and a deactivation or a new password ends
the logins of the user at once."""

import re

import pytest
from sqlalchemy import func, select

from app.main import app
from app.models import Meeting, UserRole

# Made-up account data: the password make_user (conftest.py) gives a user
PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "another-horse-battery"

# Every admin endpoint as (method, path), read from the OpenAPI description
# like PROTECTED_ENDPOINTS in test_meeting_access.py, so an admin endpoint
# added later is checked too
ADMIN_ENDPOINTS = [
    (method.upper(), path)
    for path, methods in app.openapi()["paths"].items()
    for method in methods
    if path.startswith("/api/admin/")
]


@pytest.fixture
def admin(make_user):
    return make_user(email="admin@example.com", role=UserRole.ADMIN)


@pytest.fixture
def admin_client(client_for, admin):
    return client_for(admin)


def login(client_for, email, password):
    """Log in from a new browser and return the response."""
    return client_for(None).post(
        "/api/auth/login", json={"email": email, "password": password}
    )


def test_the_admin_endpoints_are_found():
    # Makes sure the test below really has endpoints to check
    assert ("GET", "/api/admin/users") in ADMIN_ENDPOINTS
    assert ("PATCH", "/api/admin/users/{user_id}") in ADMIN_ENDPOINTS
    assert ("POST", "/api/admin/users/{user_id}/password") in ADMIN_ENDPOINTS


@pytest.mark.parametrize(
    "method, path", ADMIN_ENDPOINTS, ids=[" ".join(e) for e in ADMIN_ENDPOINTS]
)
def test_a_regular_user_gets_403_on_every_admin_endpoint(
    client, db, make_user, method, path
):
    other_user = make_user(email="other@example.com")
    password_hash = other_user.password_hash
    url = re.sub(r"\{[^}]+\}", str(other_user.id), path)

    # A body every admin endpoint would accept, so the answer would be a
    # success, not a 422, if the endpoint let a regular user in
    response = client.request(
        method, url, json={"is_active": False, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 403
    # Nothing was changed
    db.refresh(other_user)
    assert other_user.is_active is True
    assert other_user.password_hash == password_hash
    assert other_user.token_version == 0


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("PATCH", "/api/admin/users/{id}", {"is_active": False}),
        ("POST", "/api/admin/users/{id}/password", {"new_password": NEW_PASSWORD}),
    ],
    ids=["deactivate", "set password"],
)
def test_the_admin_cannot_lock_themselves_out(
    admin_client, admin, db, method, path, body
):
    password_hash = admin.password_hash

    response = admin_client.request(method, path.format(id=admin.id), json=body)

    # 400: nobody else could activate the account or log in with the password
    assert response.status_code == 400
    db.refresh(admin)
    assert admin.is_active is True
    assert admin.password_hash == password_hash
    assert admin_client.get("/api/auth/me").status_code == 200


def test_a_deactivated_user_is_locked_out_and_keeps_their_interviews(
    admin_client, client_for, db, make_user, make_meeting
):
    user = make_user()
    make_meeting(user_id=user.id)
    user_client = client_for(user)

    deactivated = admin_client.patch(
        f"/api/admin/users/{user.id}", json={"is_active": False}
    )

    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    # The cookie the user still has stops working at once, and so does the
    # login; the interview is not deleted
    assert user_client.get("/api/auth/me").status_code == 401
    assert login(client_for, user.email, PASSWORD).status_code == 401
    meetings = db.scalar(
        select(func.count()).select_from(Meeting).where(Meeting.user_id == user.id)
    )
    assert meetings == 1

    activated = admin_client.patch(
        f"/api/admin/users/{user.id}", json={"is_active": True}
    )

    assert activated.status_code == 200
    # The user can log in again, but the cookie from before stays invalid
    assert login(client_for, user.email, PASSWORD).status_code == 200
    assert user_client.get("/api/auth/me").status_code == 401


def test_a_password_set_by_the_admin_ends_every_login_of_the_user(
    admin_client, client_for, make_user
):
    user = make_user()
    user_client = client_for(user)

    response = admin_client.post(
        f"/api/admin/users/{user.id}/password", json={"new_password": NEW_PASSWORD}
    )

    assert response.status_code == 204
    assert user_client.get("/api/auth/me").status_code == 401
    assert login(client_for, user.email, PASSWORD).status_code == 401
    assert login(client_for, user.email, NEW_PASSWORD).status_code == 200


def test_a_password_set_by_the_admin_must_be_changed_before_anything_else(
    admin_client, client_for, make_user, make_meeting
):
    user = make_user()
    make_meeting(user_id=user.id)
    admin_client.post(
        f"/api/admin/users/{user.id}/password", json={"new_password": NEW_PASSWORD}
    )
    # A new browser, which keeps the cookie of the login
    user_client = client_for(None)
    user_client.post(
        "/api/auth/login", json={"email": user.email, "password": NEW_PASSWORD}
    )

    # Logged in, but only /me and the password change work
    assert user_client.get("/api/auth/me").json()["must_change_password"] is True
    assert user_client.get("/api/meetings").status_code == 403

    # The password the admin set (and knows) cannot be kept
    same = user_client.post(
        "/api/auth/password",
        json={"current_password": NEW_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert same.status_code == 400
    assert user_client.get("/api/meetings").status_code == 403

    changed = user_client.post(
        "/api/auth/password",
        json={"current_password": NEW_PASSWORD, "new_password": "own-horse-battery"},
    )

    assert changed.status_code == 204
    assert user_client.get("/api/auth/me").json()["must_change_password"] is False
    meetings = user_client.get("/api/meetings")
    assert meetings.status_code == 200
    assert len(meetings.json()) == 1
