from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    # If the database cannot be reached, this raises OperationalError, which
    # app/error_handlers.py turns into 503: the server itself works, but
    # something it depends on does not
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
