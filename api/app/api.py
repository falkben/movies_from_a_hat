"""Main entrypoint"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app import db, movies, security, users

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
app.include_router(users.router)


@app.exception_handler(security.NotAuthenticatedException)
def auth_exception_handler(request: Request, exc: security.NotAuthenticatedException):
    """
    Redirect the user to the login page if not logged in
    """

    # todo: pass along context for page they were trying to visit
    return RedirectResponse(url="/login")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
