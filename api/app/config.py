from functools import lru_cache

import httpx
from pydantic import BaseSettings, Field, HttpUrl, validator

TMDB_API_URL = "https://api.themoviedb.org/3"


class Settings(BaseSettings):

    secret: str = Field(
        ..., env="SECRET_KEY", description="A unique unpredictable value"
    )

    tmdb_api_url: str = TMDB_API_URL
    tmdb_api_key: str = Field(
        ...,
        env="TMDB_API_TOKEN",
        description="From https://www.themoviedb.org/settings/api",
    )
    tmdb_base_path: HttpUrl | None = None

    @validator("tmdb_base_path", always=True)
    def set_tmdb_base_path(cls, v, values):
        """Assign the tmdb_base_path"""

        # we use a validator here to "compute" tmdb_base_path, which requires tmdb_api_key
        # see: https://pydantic-docs.helpmanual.io/usage/validators/#validate-always

        # get configuration for poster base_url (e.g.: https://image.tmdb.org/t/p/)
        #  https://api.themoviedb.org/3/configuration?api_key=<<api_key>>

        tmdb_config_url = f"{values['tmdb_api_url']}/configuration"
        config_resp = httpx.get(
            tmdb_config_url, params={"api_key": values["tmdb_api_key"]}
        )
        return config_resp.json()["images"]["secure_base_url"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings():
    """dependency for returning settings

    Note: we use @lru_cache to avoid calling the configuration endpoint over and over
    """
    return Settings()
