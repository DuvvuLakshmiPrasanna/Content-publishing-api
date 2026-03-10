from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://cms_user:cms_password@db:5432/cms_db"
    REDIS_URL: str = "redis://redis:6379/0"
    SECRET_KEY: str = "super-secret-jwt-key-change-in-production-abc123xyz"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    MEDIA_UPLOAD_DIR: str = "/app/uploads"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
