from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import User
from app.schemas import SetPasswordRequest, UserActiveUpdate, UserRead
from app.services import users as users_service

# The errors of the service (404, 400) are turned into HTTP responses in
# app/error_handlers.py, so the endpoints here do not catch them.
#
# dependencies=: require_admin runs before every endpoint of this router,
# also the ones added later: 401 without a login, 403 for anyone who is not
# an admin. The endpoints that need the admin themselves still ask for it as
# a parameter; FastAPI runs the dependency only once per request.
router = APIRouter(
    prefix="/admin/users",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    return users_service.list_users(db)


# PATCH: for now only is_active can be changed. Returns the whole user, so
# the frontend can show it without another GET
@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    data: UserActiveUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return users_service.set_active(db, admin, user_id, data.is_active)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(
    user_id: int,
    data: SetPasswordRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users_service.set_password(db, admin, user_id, data.new_password)
