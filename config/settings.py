try:
    # pydantic v1: BaseSettings is built-in; use inner Config class
    from pydantic import BaseSettings

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

except ImportError:
    # pydantic v2: BaseSettings moved to pydantic-settings; use model_config
    from pydantic_settings import BaseSettings
    from pydantic_settings import SettingsConfigDict

    class Settings(BaseSettings):  # type: ignore[no-redef]
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
        )

        encryption_key: str
        smtp_host: str = "smtp.gmail.com"
        smtp_port: int = 587
        smtp_user: str
        smtp_password: str
        smtp_from: str
        telegram_bot_token: str = ""
        playwright_service_url: str = "http://playwright:8001"
        database_url: str = "sqlite:///./data/campbuddy.db"


def get_settings() -> Settings:
    return Settings()
