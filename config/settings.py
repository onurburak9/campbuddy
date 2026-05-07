from pydantic import BaseSettings  # pydantic v1 built-in — do NOT import from pydantic_settings


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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    return Settings()
