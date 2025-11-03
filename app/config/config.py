# app/config/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Async URL for the FastAPI app
    DATABASE_URL: str  
    
    # Sync URL for Alembic migrations
    DATABASE_URL_SYNC: str 

    # Settings for JWT Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day

    model_config = SettingsConfigDict(
             env_file=".env",
             env_file_encoding="utf-8",
             case_sensitive=False,
             extra="ignore",  # allow extra env vars (e.g. feature flags) without failing validation
         )

# Instantiate once, pull settings.DATABASE_URL elsewhere
settings = Settings()