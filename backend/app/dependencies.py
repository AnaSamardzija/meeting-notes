"""FastAPI dependencies that tell who is logged in.

An endpoint asks for the logged-in user with
    user: User = Depends(get_current_user)
and for an admin with Depends(require_admin). FastAPI runs the dependency
before the endpoint; when it raises an HTTPException, the endpoint does not
run at all.
"""

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.services.auth import decode_access_token

# The cookie that holds the login token (set in app/routers/auth.py)
ACCESS_TOKEN_COOKIE = "access_token"


def get_current_user(
    # The browser sends the cookie by itself. include_in_schema=False: it is
    # not a field to fill in /docs (a page cannot set an httpOnly cookie)
    access_token: str | None = Cookie(
        default=None, alias=ACCESS_TOKEN_COOKIE, include_in_schema=False
    ),
    db: Session = Depends(get_db),
) -> User:
    """Return the logged-in user, or answer 401.

    The user is loaded from the database on every request, so a deactivated
    user is locked out at once, not only when the token expires.
    """
    user_id = decode_access_token(access_token) if access_token else None
    user = db.get(User, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Return the logged-in user if they are an admin, or answer 403.

    401 means "we do not know who you are"; 403 means "we know, and you may
    not do this".
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user
