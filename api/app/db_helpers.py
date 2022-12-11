import sqlalchemy.exc
from fastapi import Depends, HTTPException, Request
from loguru import logger
from sqlalchemy.future import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.main import SQLModelMetaclass

from app import db
from app.security import NotAuthenticatedException, manager
from app.tables import User, UserCreate


async def get_object_or_404(session: AsyncSession, model: SQLModelMetaclass, id):
    instance = await session.get(model, id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return instance


async def get_or_create(session: AsyncSession, model: SQLModelMetaclass, **kwargs):
    instance = (await session.scalars(select(model).filter_by(**kwargs))).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        logger.info("Created {}: {}", model.__name__, kwargs)
        await session.flush()
        return instance


# if you need an update_or_create:
# https://github.com/falkben/steam-to-sqlite/blob/ea3873b9daf725e6b58af7ac70e5b8a54087886e/steam2sqlite/handler.py#L32-L48


async def commit(session: AsyncSession):
    """session.commit() with some exception handling"""
    try:
        await session.commit()
    except sqlalchemy.exc.StatementError as exc:
        logger.error("Exception during session.commit(): {}", exc)
        raise HTTPException(
            422,
            detail="Database error occurred, check params.",
        )


# This would normally be assigned to the manager's user_loader callback with:
# @manager.user_loader()
# however I couldn't get it to load the session as a dependency
# so instead, we use a separate require_login Depends function
async def get_user(
    email: str, session: AsyncSession = Depends(db.get_session)
) -> User | None:
    """
    Get a user from the db
    """

    statement = select(User).filter_by(email=email)
    if not isinstance(session, AsyncSession):
        session = await anext(session())
    user: User | None = (await session.scalars(statement)).first()
    return user


async def create_user(session: AsyncSession, user: UserCreate) -> User:

    db_user = User.from_orm(user)

    session.add(db_user)
    await commit(session)
    await session.refresh(db_user)

    logger.info("Created user: {}", user.username)

    return db_user


async def require_login(
    request: Request, session: AsyncSession = Depends(db.get_session)
):
    """Depends function for getting a user"""

    token = await manager._get_token(request)
    if token is None:
        raise NotAuthenticatedException(401)

    payload = manager._get_payload(token)
    # the identifier should be stored under the sub (subject) key
    user_identifier = payload.get("sub")
    if user_identifier is None:
        raise NotAuthenticatedException(401)

    user = await get_user(user_identifier, session)

    if user is None:
        raise NotAuthenticatedException(401)
    else:
        yield user
