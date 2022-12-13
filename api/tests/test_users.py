import pytest
from fastapi.testclient import TestClient
from fastapi_users_db_sqlmodel import SQLModelUserDatabaseAsync
from sqlmodel.ext.asyncio.session import AsyncSession

from app.tables import User, UserCreate
from app.users import UserManager

USER_DATA = {
    "email": "example@example.com",
    "password": "hunter2",
    "is_superuser": False,
}
BAD_USER_DATA = USER_DATA | {"password": "*******"}


@pytest.fixture
async def user(user_manager: UserManager):
    user = await user_manager.create(UserCreate(**USER_DATA))
    yield user


async def test_register_user(client: TestClient, session: AsyncSession):
    resp = client.post("/auth/register", json=USER_DATA)
    assert resp.status_code == 201

    user_in_db: User | None = await session.get(User, resp.json()["id"])
    assert user_in_db is not None
    assert user_in_db.email == USER_DATA["email"]


def test_register_duplicate_user(client: TestClient, user: User):
    resp = client.post("/auth/register", json=USER_DATA)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "REGISTER_USER_ALREADY_EXISTS"


def test_login_user(client: TestClient, user: User):
    resp = client.post(
        "/auth/cookie/login",
        data={
            "username": USER_DATA["email"],
            "password": USER_DATA["password"],
        },
    )
    assert resp.status_code == 200, resp.json()
    assert "movies-from-a-hat" in resp.cookies


def test_login_bad_user(client: TestClient, user: User):
    resp = client.post(
        "/auth/cookie/login",
        data={
            "username": BAD_USER_DATA["email"],
            "password": BAD_USER_DATA["password"],
        },
    )
    assert resp.status_code == 400, resp.json()
    assert resp.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


def test_logout_user(
    client: TestClient, user_db: SQLModelUserDatabaseAsync, user: User
):
    # todo: use db to get token for user instead of making a login request
    resp = client.post(
        "/auth/cookie/login",
        data={
            "username": USER_DATA["email"],
            "password": USER_DATA["password"],
        },
    )
    token = resp.cookies["movies-from-a-hat"]

    resp = client.post("/auth/cookie/logout", cookies={"movies-from-a-hat": token})
    assert resp.status_code == 200, resp.json()
    assert len(resp.cookies) == 0
    assert 'movies-from-a-hat=""' in resp.headers.get("set-cookie")


def test_logout_no_user(client: TestClient, user: User):
    resp = client.post("/auth/cookie/logout", follow_redirects=False)
    # unauthorized
    assert resp.status_code == 401


def test_logout_bad_user(client: TestClient, user: User):
    # todo: a bad token
    bad_token = ""
    resp = client.post(
        "/auth/cookie/logout",
        cookies={"movies-from-a-hat": bad_token},
        follow_redirects=False,
    )
    # if there's a bad user, we redirect to /login
    assert resp.status_code == 401


# todo: test superuser
