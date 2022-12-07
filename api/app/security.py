from fastapi_login import LoginManager

from app.config import get_secret


class NotAuthenticatedException(Exception):
    pass


# by default enable Authentication header login (bearer token)
# could be disabled with use_header=False
manager = LoginManager(
    get_secret(),
    "/login",
    use_cookie=True,
    cookie_name="movies-from-a-hat",
    custom_exception=NotAuthenticatedException,
)


def hash_password(plaintext_password: str):
    """Return the hash of a password"""
    return manager.pwd_context.hash(plaintext_password)


def verify_password(password_input: str, hashed_password: str):
    """Check if the provided password matches"""
    return manager.pwd_context.verify(password_input, hashed_password)
