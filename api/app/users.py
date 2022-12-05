"""Users routing"""


from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_login.exceptions import InvalidCredentialsException
from loguru import logger
from sqlalchemy.future import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import db, security
from app.db_helpers import commit
from app.security import manager
from app.tables import User, UserCreate, UserResponse


@manager.user_loader()
async def get_user(session: AsyncSession, email: str) -> User | None:
    """
    Get a user from the db
    """

    statement = select(User).filter_by(email=email)
    user: User | None = (await session.scalars(statement)).first()

    return user


async def get_user_attrs(session: AsyncSession, **kwargs) -> User | None:
    statement = select(User).filter_by(**kwargs)
    user: User | None = (await session.scalars(statement)).first()

    return user


async def create_user(session: AsyncSession, user: UserCreate) -> User:

    db_user = User.from_orm(user)

    session.add(db_user)
    await commit(session)
    await session.refresh(db_user)

    logger.info("Created user: {}", user.username)

    return db_user


router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, session: AsyncSession = Depends(db.get_session)):

    # todo: perhaps condense the following two queries into one
    if await get_user(session, user.email) is not None:
        raise HTTPException(
            status_code=400, detail="A user with this email already exists"
        )
    if await get_user_attrs(session, username=user.username) is not None:
        raise HTTPException(
            status_code=400, detail="A user with this username already exists"
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

    user: User | None = await get_user(session, email)
    if not user:
        raise InvalidCredentialsException
    elif not security.verify_password(password, user.password):
        raise InvalidCredentialsException

    token = manager.create_access_token(data=dict(sub=user.email))
    manager.set_cookie(response, token)

    return {"status": "Success"}
