"""Tests of registration, login, logout, the logged-in user and the admin.

Everything here is security: who can get in, and with which role.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.dependencies import ACCESS_TOKEN_COOKIE, require_admin
from app.main import app
from app.models import User, UserRole
from app.services.auth import NotAnAdminError, create_admin

# Made-up account data: the email and the password make_user (conftest.py)
# gives a user when the test does not choose them
EMAIL = "alex@example.com"
PASSWORD = "correct-horse-battery"


@pytest.fixture
def client():
    """Replaces the client of conftest.py in this file: these tests log in
    themselves. https: the login cookie is Secure, and httpx sends a Secure
    cookie back only over https."""
    return TestClient(app, base_url="https://testserver")


def register(client, email=EMAIL, password=PASSWORD, **extra_fields):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, **extra_fields},
    )


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def find_user(db, email=EMAIL) -> User | None:
    return db.scalar(select(User).where(User.email == email))


# --- Registration ---


def test_register_stores_only_a_hash_and_never_makes_an_admin(client, db):
    # "role" is not a field of the form; sending it must change nothing
    response = register(client, email="Alex@Example.com", role="admin")

    assert response.status_code == 201
    assert response.json()["role"] == "user"
    assert "password_hash" not in response.json()
    user = find_user(db)
    assert user.role == UserRole.USER
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


def test_register_logs_in_with_a_secure_http_only_strict_cookie(client):
    response = register(client)

    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith(f"{ACCESS_TOKEN_COOKIE}=")
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=strict" in cookie
    assert f"max-age={settings.jwt_expire_hours * 3600}" in cookie
    assert client.get("/api/auth/me").json()["email"] == EMAIL


def test_register_rejects_an_email_that_is_taken_in_any_case(client, make_user):
    make_user()

    response = register(client, email="ALEX@example.com")

    assert response.status_code == 409


def test_register_rejects_a_password_shorter_than_10_characters(client, db):
    response = register(client, password="123456789")

    assert response.status_code == 422
    assert find_user(db) is None


@pytest.mark.parametrize(
    "email, status_code",
    [
        ("alex@Example.com", 201),
        ("alex@other.com", 422),
        # Exactly the domain: neither a subdomain nor a longer name
        ("alex@team.example.com", 422),
        ("alex@example.com.evil.com", 422),
    ],
)
def test_register_allows_only_the_allowed_domain_when_it_is_set(
    client, monkeypatch, email, status_code
):
    monkeypatch.setattr(settings, "allowed_email_domain", "example.com")

    response = register(client, email=email)

    assert response.status_code == status_code


# --- Login and logout ---


def test_login_with_the_right_password_logs_in(client, make_user):
    make_user()

    response = login(client, email="Alex@Example.COM")

    assert response.status_code == 200
    assert ACCESS_TOKEN_COOKIE in response.cookies
    assert client.get("/api/auth/me").json()["email"] == EMAIL


@pytest.mark.parametrize(
    "email, password, is_active",
    [
        ("nobody@example.com", PASSWORD, True),
        (EMAIL, "wrong-password", True),
        # A deactivated user cannot log in, even with the right password
        (EMAIL, PASSWORD, False),
    ],
    ids=["unknown email", "wrong password", "deactivated"],
)
def test_login_fails_with_the_same_401_for_every_reason(
    client, make_user, email, password, is_active
):
    make_user(is_active=is_active)

    response = login(client, email=email, password=password)

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}
    assert "set-cookie" not in response.headers


def test_logout_deletes_the_cookie(client):
    register(client)

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


# --- The logged-in user (get_current_user) ---


def test_me_without_a_cookie_is_401(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def _expired_token(user_id: int) -> str:
    past = datetime.now(UTC) - timedelta(minutes=1)
    return jwt.encode(
        {"sub": str(user_id), "exp": past}, settings.jwt_secret, algorithm="HS256"
    )


def _token_signed_with_another_secret(user_id: int) -> str:
    future = datetime.now(UTC) + timedelta(hours=1)
    return jwt.encode(
        {"sub": str(user_id), "exp": future},
        "another-secret-that-is-at-least-32-chars",
        algorithm="HS256",
    )


def _unsigned_token(user_id: int) -> str:
    # alg "none": a token with no signature at all
    future = datetime.now(UTC) + timedelta(hours=1)
    return jwt.encode({"sub": str(user_id), "exp": future}, None, algorithm="none")


def _token_with_version(user_id: int, version: int | None) -> str:
    # A correctly signed token; version None leaves "ver" out, as in the
    # tokens made before it was added
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    if version is not None:
        payload["ver"] = version
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


@pytest.mark.parametrize(
    "make_token",
    [
        _expired_token,
        _token_signed_with_another_secret,
        _unsigned_token,
        lambda user_id: "not-a-jwt",
        lambda user_id: _token_with_version(user_id, None),
        # The user's token_version is 0: a token of another version is one
        # from before (or after) a password change
        lambda user_id: _token_with_version(user_id, 1),
    ],
    ids=[
        "expired",
        "another secret",
        "unsigned",
        "not a jwt",
        "without a version",
        "another version",
    ],
)
def test_me_with_an_invalid_token_is_401(client, make_user, make_token):
    user = make_user()
    client.cookies.set(ACCESS_TOKEN_COOKIE, make_token(user.id))

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_a_user_deactivated_after_login_is_locked_out_at_once(client, db):
    register(client)
    user = find_user(db)
    user.is_active = False
    db.commit()

    response = client.get("/api/auth/me")

    assert response.status_code == 401


# --- Password change ---

NEW_PASSWORD = "another-horse-battery"


def change_password(client, current_password=PASSWORD, new_password=NEW_PASSWORD):
    return client.post(
        "/api/auth/password",
        json={"current_password": current_password, "new_password": new_password},
    )


def test_a_wrong_current_password_changes_nothing_and_keeps_the_login(client, db):
    register(client)
    user = find_user(db)
    password_hash = user.password_hash

    response = change_password(client, current_password="wrong-password")

    # 400, not 401: the frontend would log the user out on a 401
    assert response.status_code == 400
    db.refresh(user)
    assert user.password_hash == password_hash
    assert user.token_version == 0
    assert client.get("/api/auth/me").status_code == 200


def test_a_password_change_logs_out_every_other_browser(client, make_user):
    make_user()
    login(client)
    # Another browser logged in with the same account before the change
    other_browser = TestClient(app, base_url="https://testserver")
    login(other_browser)

    response = change_password(client)

    assert response.status_code == 204
    # This browser got a new cookie and stays logged in; the other is out
    assert ACCESS_TOKEN_COOKIE in response.cookies
    assert client.get("/api/auth/me").status_code == 200
    assert other_browser.get("/api/auth/me").status_code == 401
    # Only the new password works from now on
    assert login(TestClient(app, base_url="https://testserver")).status_code == 401
    new_login = login(
        TestClient(app, base_url="https://testserver"), password=NEW_PASSWORD
    )
    assert new_login.status_code == 200


# --- Admin ---


def test_require_admin_lets_only_an_admin_through(make_user):
    regular_user = make_user()
    admin = make_user(email="admin@example.com", role=UserRole.ADMIN)

    with pytest.raises(HTTPException) as error:
        require_admin(regular_user)
    assert error.value.status_code == 403
    assert require_admin(admin) is admin


def test_create_admin_creates_the_admin_once_and_then_changes_nothing(db):
    assert create_admin(db, "Admin@Example.com", PASSWORD) is True
    admin = find_user(db, "admin@example.com")
    assert admin.role == UserRole.ADMIN
    password_hash = admin.password_hash

    # Run again, with another password in .env: the admin stays as it was
    assert create_admin(db, "admin@example.com", "another-password") is False
    db.refresh(admin)
    assert admin.password_hash == password_hash


def test_create_admin_never_makes_a_regular_user_an_admin(db, make_user):
    user = make_user()
    password_hash = user.password_hash

    with pytest.raises(NotAnAdminError):
        create_admin(db, EMAIL, "admin-password-from-env")

    db.refresh(user)
    assert user.role == UserRole.USER
    assert user.password_hash == password_hash
