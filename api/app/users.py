import uuid

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users_db_sqlmodel.access_token import (
    SQLModelAccessTokenDatabase,
    SQLModelAccessTokenDatabaseAsync,
)
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session, get_user_db
from app.tables import AccessToken, User


async def get_access_token_db(session: AsyncSession = Depends(get_session)):
    yield SQLModelAccessTokenDatabaseAsync(session, AccessToken)


def get_database_strategy(
    access_token_db: SQLModelAccessTokenDatabase[AccessToken] = Depends(
        get_access_token_db
    ),
) -> DatabaseStrategy:
    return DatabaseStrategy(access_token_db, lifetime_seconds=None)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    def __init__(self, *args, **kwargs):
        """User __init__ here to set secret (instead of as a class attribute) so it's
        not done at import time which helps with initializing tests with mocked secret
        value"""

        super().__init__(*args, **kwargs)
        self.reset_password_token_secret = get_settings().secret
        self.verification_token_secret = get_settings().secret

    async def on_after_register(self, user: User, request: Request | None = None):
        logger.info("User {} has registered.", user.id)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ):
        logger.info("User {} has forgot their password. Reset token", user.id)

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ):
        logger.info("Verification requested for user {}.", user.id)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


def get_cookie_transport():
    return CookieTransport(
        cookie_name="movies-from-a-hat",
        cookie_max_age=None,
        cookie_secure=get_settings().cookie_secure,
        cookie_domain=get_settings().cookie_domain,
        cookie_samesite=get_settings().cookie_samesite,
    )


def get_auth_backend():
    return AuthenticationBackend(
        name="cookie",
        transport=get_cookie_transport(),
        get_strategy=get_database_strategy,
    )
