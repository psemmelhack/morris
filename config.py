from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str

    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str  # Your personal chat ID

    # Tavily
    tavily_api_key: str

    # Resend (email)
    resend_api_key: str
    reminder_email_to: str
    reminder_email_from: str = "morris@yourdomain.com"

    # Database
    database_url: str  # postgresql://user:pass@host:5432/morris

    # Location
    user_location: str = "Shelter Island, NY"
    user_timezone: str = "America/Los_Angeles"  # PT

    # Scheduler
    morning_hour: int = 6
    morning_minute: int = 0

    class Config:
        env_file = ".env"


settings = Settings()
