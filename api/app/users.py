"""Users routing"""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_login.exceptions import InvalidCredentialsException
from loguru import logger
from sqlalchemy import or_
from sqlalchemy.future import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import db, security
from app.db_helpers import create_user, get_user, require_login
from app.security import manager
from app.tables import User, UserCreate, UserResponse

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, session: AsyncSession = Depends(db.get_session)):

    # todo: consider generalizing and moving to db_helpers
    statement = select(User.id).filter(
        or_(User.email == user.email, User.username == user.username)
    )
    existing_user_id = (await session.scalars(statement)).first()

    if existing_user_id is not None:
        raise HTTPException(
            status_code=400, detail="A user with this email or username already exists"
        )

    db_user = await create_user(session, user)
    return db_user


@router.post("/login")
async def login(
    response: Response,
    data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(db.get_session),
):
    email = data.username
    password = data.password

    user: User | None = await get_user(email, session)
    if not user:
        raise InvalidCredentialsException
    elif not security.verify_password(password, user.password):
        raise InvalidCredentialsException

    token = manager.create_access_token(data={"sub": user.email})
    manager.set_cookie(response, token)

    logger.info("Logged in user {}", user.email)

    return {"status": "Success"}


@router.post("/logout")
async def logout(
    response: Response,
    # session: AsyncSession = Depends(db.get_session),
    user: User = Depends(require_login),
):

    response.delete_cookie(manager.cookie_name)

    logger.info("Logged out user {}", user.email)

    return {"status": "Success"}
