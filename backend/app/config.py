from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# .env in the project root (shared with docker compose), regardless of the
# directory the server is started from
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


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
