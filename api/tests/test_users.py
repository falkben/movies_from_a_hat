import pytest
from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.security import auth_config
from app.tables import User, UserCreate

USER_DATA = {
    "email": "example@example.com",
    "password": "hunter2",
    "username": "example",
    "is_admin": False,
}
BAD_USER_DATA = USER_DATA | {"password": "*******"}


@pytest.fixture()
async def default_user(session: AsyncSession):
    # we use the UserCreate model here in order to run the hash on the password
    user = UserCreate(**USER_DATA)
    user_db = User.from_orm(user)
    session.add(user_db)
    await session.commit()
    await session.refresh(user_db)
    yield user_db


async def test_register_user(client: TestClient, session: AsyncSession):
    resp = client.post("/register", json=USER_DATA)
    assert resp.status_code == 200

    user_in_db: User | None = await session.get(User, resp.json()["id"])
    assert user_in_db is not None
    assert user_in_db.email == USER_DATA["email"]


def test_register_duplicate_user(client: TestClient, default_user: User):
    resp = client.post("/register", json=USER_DATA)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "A user with this email or username already exists"


def test_login_user(client: TestClient, default_user: User):
    resp = client.post(
        "/login",
        data={
            "username": USER_DATA["email"],
            "password": USER_DATA["password"],
        },
    )
    assert resp.status_code == 200, resp.json()
    assert "movies-from-a-hat" in resp.cookies
    # todo: check cookie


def test_login_bad_user(client: TestClient, default_user: User):
    resp = client.post(
        "/login",
        data={
            "username": BAD_USER_DATA["email"],
            "password": BAD_USER_DATA["password"],
        },
    )
    assert resp.status_code == 401, resp.json()


def test_logout_user(client: TestClient, default_user: User):
    token = auth_config.manager().create_access_token(data={"sub": default_user.email})
    resp = client.post("/logout", cookies={auth_config.manager().cookie_name: token})
    assert resp.status_code == 200, resp.json()
    assert len(resp.cookies) == 0
    assert resp.json() == {"status": "Success"}
    assert 'movies-from-a-hat=""' in resp.headers.get("set-cookie")


def test_logout_no_user(client: TestClient, default_user: User):
    resp = client.post("/logout", follow_redirects=False)
    # if there's no user, we redirect to /login
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_logout_bad_user(client: TestClient, default_user: User):
    token = auth_config.manager().create_access_token(data={"sub": "BAD_USER_EMAIL"})
    resp = client.post(
        "/logout",
        cookies={auth_config.manager().cookie_name: token},
        follow_redirects=False,
    )
    # if there's a bad user, we redirect to /login
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


# todo: test is_admin user
