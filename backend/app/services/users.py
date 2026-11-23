"""What the admin does with the accounts of the users.

Users are never deleted, only deactivated: their interviews stay, and an
account can be activated again. These functions do not check that the caller
is an admin; the router does that (require_admin).
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.services.auth import hash_password


# The messages of these errors are written for the user. The service knows
# nothing about HTTP: app/error_handlers.py decides the status codes.
class UserNotFoundError(Exception):
    """There is no user with the given id."""


class OwnAccountError(Exception):
    """The admin tried to deactivate their own account, or to set their own
    password without the current one."""


def list_users(db: Session) -> Sequence[User]:
    """Return every user, deactivated ones too, by email."""
    return db.scalars(select(User).order_by(User.email)).all()


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError("User not found")
    return user


def set_active(db: Session, admin: User, user_id: int, is_active: bool) -> User:
    """Activate or deactivate the account and return the user.

    Raises UserNotFoundError, or OwnAccountError when the admin tries to
    deactivate themselves: nobody could activate the account again.
    """
    if user_id == admin.id and not is_active:
        raise OwnAccountError("You cannot deactivate your own account")
    user = _get_user(db, user_id)
    if user.is_active and not is_active:
        # A deactivated user is locked out at once anyway (get_current_user
        # checks is_active). The new token version also makes sure that the
        # tokens from before do not work again when the account is activated:
        # the user then has to log in again.
        user.token_version += 1
    user.is_active = is_active
    db.commit()
    return user


def set_password(db: Session, admin: User, user_id: int, new_password: str) -> None:
    """Give the user a new password, e.g. when they forgot theirs.

    token_version goes up, so every login of the user made before stops
    working. The admin knows this password, so the user must change it after
    logging in (must_change_password). Raises UserNotFoundError, or OwnAccountError for the admin's own
    account: the admin changes their password on the profile page, which asks
    for the current one and keeps them logged in.
    """
    if user_id == admin.id:
        raise OwnAccountError(
            "Change your own password on the profile page"
        )
    user = _get_user(db, user_id)
    user.password_hash = hash_password(new_password)
    user.token_version += 1
    user.must_change_password = True
    db.commit()
