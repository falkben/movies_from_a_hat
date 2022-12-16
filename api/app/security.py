import datetime

from fastapi import Response
from fastapi_login import LoginManager

from app.config import get_secret, get_settings


class NotAuthenticatedException(Exception):
    pass


class AuthConfig:
    def __init__(self) -> None:
        self._manager: LoginManager | None = None

    def manager(self) -> LoginManager:
        if not self._manager:
            self._manager = LoginManager(
                get_secret(),
                "/login",
                use_header=False,
                use_cookie=True,
                cookie_name="movies-from-a-hat",
                custom_exception=NotAuthenticatedException,
                default_expiry=datetime.timedelta(
                    seconds=get_settings().cookie_max_age
                ),  # token will expire even if cookie doesn't
            )
        return self._manager

    def hash_password(self, plaintext_password: str):
        """Return the hash of a password"""
        return self.manager().pwd_context.hash(plaintext_password)

    def verify_password(self, password_input: str, hashed_password: str):
        """Check if the provided password matches"""
        return self.manager().pwd_context.verify(password_input, hashed_password)

    def set_cookie(self, response: Response, token: str):
        response.set_cookie(
            self.manager().cookie_name,
            value=token,
            httponly=True,
            max_age=get_settings().cookie_max_age,
            secure=get_settings().cookie_secure,
            samesite=get_settings().cookie_samesite,
            domain=get_settings().cookie_domain,
        )


auth_config = AuthConfig()
