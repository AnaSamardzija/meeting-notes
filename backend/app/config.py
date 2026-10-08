from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

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


settings = Settings()
