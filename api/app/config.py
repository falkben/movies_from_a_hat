from functools import lru_cache

from pydantic import BaseSettings, Field

TMDB_API_URL = "https://api.themoviedb.org/3"


class Settings(BaseSettings):

    tmdb_api_url: str = TMDB_API_URL
    tmdb_api_key: str = Field(
        ...,
        env="TMDB_API_TOKEN",
        description="From https://www.themoviedb.org/settings/api",
    )
    secret: str = Field(
        ..., env="SECRET_KEY", description="A unique unpredictable value"
    )

    # security
    cookie_secure: bool = Field(False, env="COOKIE_SECURE")
    cookie_domain: str | None = Field(None, env="COOKIE_DOMAIN")
    cookie_samesite: str = Field("lax", env="COOKIE_SAMESITE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """dependency for returning settings

    Note: we use @lru_cache to avoid calling the configuration endpoint over and over
    """
    return Settings()
