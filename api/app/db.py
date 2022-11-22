from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

database_conn_str = "sqlite+aiosqlite:///database.sqlite"
engine = create_async_engine(database_conn_str, echo=False)


# todo: replace with Alembic
async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session():
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,  # pyright: ignore [reportGeneralTypeIssues]
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session
