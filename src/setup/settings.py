
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    # DB
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