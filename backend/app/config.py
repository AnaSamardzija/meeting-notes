from pathlib import Path

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
