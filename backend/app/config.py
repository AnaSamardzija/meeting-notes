from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# .env in the project root (shared with docker compose), regardless of the
# directory the server is started from
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR.parent / ".env"


class Settings(BaseSettings):
    # extra="ignore": the root .env also holds variables the backend does not use
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # Origins that are allowed to call the API (CORS), separated by commas
    cors_origins: str = "http://localhost:5173"

    # Lowest level of the log messages that are printed. Literal: any other
    # value in .env stops the app at startup with a clear error
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Database. The MYSQL_* values have no default on purpose: the app fails
    # at startup with a clear error if they are missing from .env
    mysql_user: str
    mysql_password: str
    mysql_database: str
    db_host: str = "localhost"
    db_port: int = 3306

    # Uploads. A relative UPLOAD_DIR is resolved from the backend/ folder
    upload_dir: Path = Path("uploads")
    max_upload_mb: int = 500

    # Longest time ffmpeg may take to extract the audio from one video
    ffmpeg_timeout_seconds: int = 600

    # Gemini. The key has no default on purpose, like the MYSQL_* values
    gemini_api_key: str
    gemini_model: str = "gemini-3.8-flash"
    # Longest time one request to Gemini may take
    gemini_timeout_seconds: int = 600

    # Login. The secret signs the JWT in the login cookie: anyone who knows it
    # can make a token for any user. No default on purpose, and at least 32
    # characters, because a short secret can be guessed
    jwt_secret: str = Field(min_length=32)
    # How long a login lasts; the cookie and the token expire together
    jwt_expire_hours: int = Field(default=12, gt=0)
    # When set (for example example.com), only addresses with exactly this
    # domain can register. Empty: any address can
    allowed_email_domain: str = ""

    @property
    def upload_path(self) -> Path:
        # Joining with an absolute path returns that absolute path unchanged,
        # so UPLOAD_DIR=/data/uploads (Docker) works as well
        return BACKEND_DIR / self.upload_dir

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def database_url(self) -> URL:
        # Built from the parts so the password lives in one place only.
        # URL.create also escapes special characters in the password.
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password,
            host=self.db_host,
            port=self.db_port,
            database=self.mysql_database,
            query={"charset": "utf8mb4"},
        )


settings = Settings()
