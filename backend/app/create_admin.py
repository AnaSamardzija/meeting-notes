"""Create the first admin from ADMIN_EMAIL and ADMIN_PASSWORD in .env.

Run from the backend/ folder:
    python -m app.create_admin

It can run any number of times: when the admin already exists, nothing is
changed (the password neither). The password in .env is used only when the
account is created; after that the admin changes it in the app.
"""

import sys

from pydantic import EmailStr, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import ENV_FILE
from app.database import SessionLocal
from app.schemas import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.services.auth import NotAnAdminError, create_admin


class AdminSettings(BaseSettings):
    """Read only by this command, so the web app never loads the admin's
    password. The same rules as registration, except the email domain."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    admin_email: EmailStr
    admin_password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


def main() -> int:
    """Return the exit code: 0 when the admin exists afterwards, 1 on error."""
    try:
        admin = AdminSettings()
    except ValidationError as error:
        # Only the name of the variable and the rule it breaks: str(error)
        # would also print the value, which can be the password
        for problem in error.errors():
            name = str(problem["loc"][0]).upper()
            print(f"Error: {name}: {problem['msg']}", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        try:
            created = create_admin(db, admin.admin_email, admin.admin_password)
        except NotAnAdminError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    if created:
        print(f"Admin {admin.admin_email} created.")
    else:
        print(f"Admin {admin.admin_email} already exists; nothing changed.")
    return 0


# True only when the file is run as a command (python -m app.create_admin),
# not when it is imported
if __name__ == "__main__":
    sys.exit(main())
