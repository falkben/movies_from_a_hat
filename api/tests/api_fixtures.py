"""api/app fixtures

fixtures that depend on app import
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import app
from app.db import get_session


@pytest.fixture(name="client")
async def client_fixture(session: AsyncSession):
    """Create the test client

    Overrides the session dependency in our endpoints to use this session instead

    Note that because we create the database tables with a startup event
    (using create_db_and_tables), this fixture must occur in the parameter list before
    other database access fixtures.

    E.g. works:

    def my_test_func(client: TestClient, dude_movie: Movie): ...

    Doesn't work, because dude_movie fixture tries to access database tables:

    def my_test_func(dude_movie: Movie, client: TestClient): ...
    """

    def get_session_override() -> AsyncSession:
        return session

    # Set the dependency override in the app.dependency_overrides dictionary.
    app.dependency_overrides[get_session] = get_session_override

    # context manager runs the app startup/shutdown/lifespan events
    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
