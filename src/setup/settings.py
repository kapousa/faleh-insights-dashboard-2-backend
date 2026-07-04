
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    stripe_api_key: str
    frontend_url: str
    stripe_report_price_id: str
    internal_webhook_secret: str
    stripe_webhook_secret: str
    n8n_forward_url: str
    database_url: str

    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # This allows the class to ignore any other variables in .env
        # that aren't defined here, preventing future crashes.
        extra="ignore"
    )

settings = Settings()