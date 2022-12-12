"""Main entrypoint"""

import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users import FastAPIUsers

from app import db, movies
from app.tables import User, UserCreate, UserRead
from app.users import auth_backend, get_user_manager

app = FastAPI()


# todo: remove once we have a proxy
# to verify w/ curl: curl -H "Origin: http://localhost" http://127.0.0.1:8000/ -v
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http[s]?://(localhost|127.0.0.1)(:[0-9]*)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await db.create_db_and_tables()


app.include_router(movies.router)

# add users routers

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

# adds /login and /logout routes
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/cookie",
    tags=["auth"],
)
# adds /register routes
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
# adds /forgot-password and /reset-password routes
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
