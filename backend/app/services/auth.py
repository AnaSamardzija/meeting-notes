"""Users and login: password hashes, login tokens, registration, admin."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserRole

# HS256: the token is signed with JWT_SECRET, and only this server checks it
JWT_ALGORITHM = "HS256"

# argon2id with the library's recommended settings. The hash it returns holds
# the algorithm, the settings and a random salt, so verify() needs nothing else
_hasher = PasswordHasher()

# Checked when the email is unknown, so a login with an unknown email takes as
# long as one with a wrong password and the response time does not reveal
# which emails have an account
_DUMMY_HASH = _hasher.hash("not-a-real-password")


# The messages of these errors are written for the user. The service knows
# nothing about HTTP: app/error_handlers.py decides the status codes.
class EmailTakenError(Exception):
    """An account with this email already exists."""


class EmailDomainNotAllowedError(Exception):
    """The email does not have the domain set in ALLOWED_EMAIL_DOMAIN."""


class InvalidCredentialsError(Exception):
    """Wrong email or password, or a deactivated account. One error for all
    of them, so the response does not reveal which one it was."""


class WrongPasswordError(Exception):
    """The current password given for a password change is not right."""


class SamePasswordError(Exception):
    """The new password is the same as the current one."""


class NotAnAdminError(Exception):
    """create_admin found a regular user with the admin's email."""


def normalize_email(email: str) -> str:
    # Stored and looked up in lower case, so Ana@Example.com and
    # ana@example.com are the same account
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        # VerificationError: the password does not match. InvalidHashError:
        # the stored value is not an argon2 hash. Neither lets anyone in
        return False


def create_access_token(user: User) -> str:
    """Return a signed token that says who the user is and until when."""
    now = datetime.now(UTC)
    payload = {
        # "sub" (subject) must be a string in a JWT
        "sub": str(user.id),
        # The token works only while the user's token_version is the same,
        # so a password change ends every older login
        "ver": user.token_version,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> tuple[int, int] | None:
    """Return the user id and the token version from a token, or None when
    the token is not valid (wrong signature, expired, changed, made before
    "ver" was added, or not a JWT at all)."""
    try:
        # algorithms: only HS256 is accepted, so a token cannot choose a
        # weaker algorithm (or "none") for itself. decode also checks "exp"
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "ver"]},
        )
        return int(payload["sub"]), int(payload["ver"])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        return None


def _check_email_domain(email: str) -> None:
    allowed = normalize_email(settings.allowed_email_domain)
    if not allowed:
        return
    # Exactly this domain: a subdomain or a longer name does not count
    if email.rsplit("@", 1)[1] != allowed:
        raise EmailDomainNotAllowedError(
            f"Only @{allowed} addresses can register"
        )


def register_user(db: Session, email: str, password: str) -> User:
    """Create a regular user. An admin can never be made here."""
    email = normalize_email(email)
    _check_email_domain(email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailTakenError("An account with this email already exists")

    user = User(email=email, password_hash=hash_password(password), role=UserRole.USER)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two registrations with the same email at the same moment: both pass
        # the check above, and the unique index stops the second one
        db.rollback()
        raise EmailTakenError("An account with this email already exists") from None
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    """Return the user with this email and password, if they may log in."""
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        verify_password(_DUMMY_HASH, password)
        raise InvalidCredentialsError("Incorrect email or password")
    if not verify_password(user.password_hash, password) or not user.is_active:
        raise InvalidCredentialsError("Incorrect email or password")
    return user


def change_password(
    db: Session, user: User, current_password: str, new_password: str
) -> None:
    """Set a new password after checking the current one.

    token_version goes up, so every login token made before (in this browser
    and in any other) stops working; the caller gives this browser a new one.
    The new password must differ from the current one: otherwise a user could
    keep the password the admin set (and knows). After the change the user
    no longer has to change it (must_change_password).
    """
    if not verify_password(user.password_hash, current_password):
        raise WrongPasswordError("The current password is incorrect")
    if verify_password(user.password_hash, new_password):
        raise SamePasswordError(
            "The new password must be different from the current one"
        )
    user.password_hash = hash_password(new_password)
    user.token_version += 1
    user.must_change_password = False
    db.commit()


def create_admin(db: Session, email: str, password: str) -> bool:
    """Create an admin; return False when this admin already exists.

    An existing admin is left as it is (the password too), so the command can
    run any number of times. A regular user is never made an admin: anyone
    could have registered that email, with a password of their own.
    """
    email = normalize_email(email)
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        if existing.role == UserRole.ADMIN:
            return False
        raise NotAnAdminError(
            f"A regular user with the email {email} already exists; "
            "it was not made an admin"
        )

    db.add(User(email=email, password_hash=hash_password(password), role=UserRole.ADMIN))
    db.commit()
    return True
