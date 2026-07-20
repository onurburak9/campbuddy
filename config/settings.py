import base64
from functools import lru_cache

from pydantic import BaseSettings, validator  # pydantic v1 built-in


class Settings(BaseSettings):
    encryption_key: str
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_from: str
    telegram_bot_token: str = ""
    playwright_service_url: str = "http://playwright:8001"
    database_url: str = "sqlite:///./data/campbuddy.db"
    api_secret_key: str = ""
    cookie_secure: bool = False
    ridb_api_key: str = ""
    registration_enabled: bool = True
    app_base_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("encryption_key")
    def _valid_fernet_key(cls, v: str) -> str:
        try:
            raw = base64.urlsafe_b64decode(v)
        except Exception as e:
            raise ValueError(f"ENCRYPTION_KEY must be valid url-safe base64: {e}")
        if len(raw) != 32:
            raise ValueError(
                f"ENCRYPTION_KEY must decode to exactly 32 bytes, got {len(raw)}"
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
