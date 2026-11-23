from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import (
    ACCESS_TOKEN_COOKIE,
    get_current_user_allow_temporary_password,
)
from app.models import User
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UserRead,
)
from app.services import auth as auth_service

# The errors of the service (401, 409, 422) are turned into HTTP responses in
# app/error_handlers.py, so the endpoints here do not catch them.
router = APIRouter(prefix="/auth", tags=["auth"])

# The attributes of the login cookie. Deleting a cookie needs the same ones,
# or the browser keeps the old cookie.
# - httponly: JavaScript in the page cannot read the token, so a script
#   injected into the page cannot steal it
# - secure: sent only over https (browsers treat http://localhost as secure,
#   so local development works too)
# - samesite="strict": not sent when another site sends a request to the API,
#   which protects against CSRF
COOKIE_OPTIONS = {"path": "/", "secure": True, "httponly": True, "samesite": "strict"}


def _set_login_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        auth_service.create_access_token(user),
        # The cookie expires together with the token in it
        max_age=settings.jwt_expire_hours * 3600,
        **COOKIE_OPTIONS,
    )


# response: Response is the response FastAPI will send; the endpoint adds the
# cookie to it and still returns the user as the body
@router.post(
    "/register", response_model=UserRead, status_code=status.HTTP_201_CREATED
)
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    user = auth_service.register_user(db, data.email, data.password)
    _set_login_cookie(response, user)
    return user


@router.post("/login", response_model=UserRead)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, data.email, data.password)
    _set_login_cookie(response, user)
    return user


# Needs no login: it only tells the browser to delete the cookie. The token
# itself stays valid until it expires, but the browser no longer has it.
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout():
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(ACCESS_TOKEN_COOKIE, **COOKIE_OPTIONS)
    return response


# /me and /password also work for a user who must change the password the
# admin set: the frontend needs to know who is logged in, and the password
# change is the way out. Every other endpoint answers 403 to such a user.
@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user_allow_temporary_password)):
    return user


# The password change ends every other login (see change_password); this
# browser gets a new cookie with the new token version and stays logged in
@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: ChangePasswordRequest,
    response: Response,
    user: User = Depends(get_current_user_allow_temporary_password),
    db: Session = Depends(get_db),
):
    auth_service.change_password(db, user, data.current_password, data.new_password)
    _set_login_cookie(response, user)
