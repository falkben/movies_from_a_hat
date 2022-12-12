import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import respx
from _pytest.logging import LogCaptureFixture
from faker import Faker
from fastapi_users_db_sqlmodel import SQLModelUserDatabaseAsync
from httpx import Response
from loguru import logger
from respx.patterns import M
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.future import Engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

from app import config
from app.db import get_user_db
from app.users import get_user_manager


@pytest.fixture
def caplog(caplog: LogCaptureFixture):
    """Allows pytest's caplog to work by adding a new handler on caplog

    Note: this does not match the application's handler exactly.

    https://loguru.readthedocs.io/en/stable/resources/migration.html#making-things-work-with-pytest-and-caplog
    """

    handler_id = logger.add(caplog.handler, format="{message}")
    yield caplog
    logger.remove(handler_id)


def pytest_configure(config):
    # in api, secret config needs to be present at import time because it's used
    # to create the login manager decorator
    # pytest_configure is a hook that runs at pytest startup, before anything else
    os.environ["SECRET_KEY"] = "secret"


@pytest.fixture(autouse=True)
def patch_env_var(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TMDB_API_TOKEN", "TESTING")


@pytest.fixture(name="engine")
def engine_fixture():
    """create an in memory sqlite database"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # after we switch to alembic instead of app startup event, need to initialize tables
    # from sqlmodel import SQLModel
    # SQLModel.metadata.create_all(engine)

    yield engine


@pytest.fixture(autouse=True)
def patch_engine(engine: Engine):
    """patch the app engine so that events use this value"""
    with patch("app.db.engine", engine):
        yield


@pytest.fixture(name="session")
async def session_fixture(engine: Engine):
    """This session fixture is used in our tests when we need to access the db"""
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,  # pyright: ignore [reportGeneralTypeIssues]
        expire_on_commit=False,
    )
    async with async_session_factory() as session:
        yield session


@pytest.fixture(name="user_db")
async def user_db_fixture(session: AsyncSession):
    async for user_db in get_user_db(session):
        yield user_db


@pytest.fixture(name="user_manager")
async def user_manager_fixture(user_db: SQLModelUserDatabaseAsync):
    async for user_manager in get_user_manager(user_db):
        yield user_manager


@pytest.fixture
async def mocked_TMDB_config_req(respx_mock):

    mocked_tmdb_config_data = {
        "images": {
            "base_url": "http://image.tmdb.org/t/p/",
            "secure_base_url": "https://image.tmdb.org/t/p/",
            "backdrop_sizes": ["w300", "w780", "w1280", "original"],
            "logo_sizes": ["w45", "w92", "w154", "w185", "w300", "w500", "original"],
            "poster_sizes": ["w92", "w154", "w185", "w342", "w500", "w780", "original"],
            "profile_sizes": ["w45", "w185", "h632", "original"],
            "still_sizes": ["w92", "w185", "w300", "original"],
        },
        # note: there's a list of "change_keys" in the response but we're not using that data
    }
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(f"{config.TMDB_API_URL}/configuration").mock(
            return_value=Response(200, json=mocked_tmdb_config_data)
        )

        yield respx_mock


@pytest.fixture(name="settings")
async def settings_fixture(mocked_TMDB_config_req):
    yield config.get_settings()


@pytest.fixture
async def mocked_TMDB():

    fake = Faker()
    fake.set_arguments("title", {"max_nb_chars": 50})
    fake.set_arguments("overview", {"nb_words": 30})
    fake.set_arguments("poster", {"text": "???????????????????????????.jpg"})
    fake_tmdb_json = (
        '{ "results": '
        + fake.json(
            data_columns={
                "id": "pyint",
                "title": "text:title",
                "overview": "sentence:overview",
                "release_date": "date",
                "poster_path": "lexify:poster",
                "genre_ids": ["pyint", "pyint", "pyint"],
            },
            num_rows=10,
        )
        + "}"
    )

    with respx.mock(assert_all_called=False) as respx_mock:
        tmdb_route = respx_mock.get(
            f"{config.TMDB_API_URL}/search/movie", name="search_tmdb_movies"
        )
        tmdb_route.return_value = Response(200, text=fake_tmdb_json)
        yield respx_mock


@pytest.fixture
async def mocked_TMDB_movie_results(request):
    # test data location relative to the test file
    file = Path(request.node.fspath.strpath)
    movies_data = {
        "115": json.load(open(file.parent / "test_data" / "115.json")),
        "550": json.load(open(file.parent / "test_data" / "550.json")),
        "6978": json.load(open(file.parent / "test_data" / "6978.json")),
    }

    with respx.mock(assert_all_called=False) as respx_mock:
        for tmdb_id, movie_data in movies_data.items():
            respx_mock.get(f"{config.TMDB_API_URL}/movie/{tmdb_id}").mock(
                return_value=Response(200, json=movie_data)
            )

        # for all others -- return 404
        # For M instance usage, see: https://lundberg.github.io/respx/api/#m
        pattern = M(url__regex=rf"{config.TMDB_API_URL}/movie/*")
        respx_mock.route(pattern).mock(
            return_value=Response(
                404,
                json={
                    "success": False,
                    "status_code": 34,
                    "status_message": "The resource you requested could not be found.",
                },
            )
        )

        yield respx_mock
