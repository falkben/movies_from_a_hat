import re
import uuid
from datetime import date, datetime

from fastapi_users import schemas
from fastapi_users_db_sqlmodel import SQLModelBaseUserDB
from fastapi_users_db_sqlmodel.access_token import SQLModelBaseAccessToken
from pydantic import validator
from sqlalchemy import CheckConstraint, Column, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlmodel import Field, Relationship, SQLModel

# todo: Groups (m2m w/ Users if users can belong to many groups)
# todo: Watched (date) is M2M with Groups & Movies/Users & Movies

# earliest movie (https://www.imdb.com/title/tt2221420/)
RELEASE_DATE_CONSTR = date(1871, 1, 1)

# regex for date in yyyy-mm-dd format
re_date_format = re.compile("^([0-9]{4})-?(1[0-2]|0[1-9])-?(3[01]|0[1-9]|[12][0-9])$")


class User(SQLModelBaseUserDB, table=True):
    pass


class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


class AccessToken(SQLModelBaseAccessToken, table=True):
    pass


class GenreMovieLink(SQLModel, table=True):
    genre_id: int | None = Field(default=None, foreign_key="genre.id", primary_key=True)
    movie_id: int | None = Field(default=None, foreign_key="movie.id", primary_key=True)


class Genre(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("name"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str
    movies: list["Movie"] = Relationship(
        back_populates="genres",
        link_model=GenreMovieLink,
        sa_relationship_kwargs={"lazy": "joined"},
    )


class MovieBase(SQLModel):
    title: str = Field(default=..., index=True)
    release_date: date = Field(default=...)
    runtime: int | None = Field(default=None, index=True)
    tmdb_id: int | None = Field(default=None, description="TMDB ID", index=True)
    imdb_id: str | None = Field(default=None, description="IMBD ID")
    poster: str | None = Field(default=None, description="TMDB poster path")
    # note: MPAA rating is under release_dates in TMDB
    # http://api.themoviedb.org/3/movie/550?api_key=###&append_to_response=release_dates
    rating: str | None = Field(default=None, description="MPAA rating")
    adult: bool = False

    @validator("release_date", pre=True)
    def release_date_format(cls, value):
        if isinstance(value, str):
            # if it's not a date already validate we are using the right format
            assert re.match(
                re_date_format, value
            ), "release_date must be in YYYY-MM-DD format"
        return value

    @validator("release_date")
    def release_date_validation(cls, value):
        assert (
            value > RELEASE_DATE_CONSTR
        ), f"release_date must be greater than {RELEASE_DATE_CONSTR.strftime('%Y-%m-%d')}"
        return value


class Movie(MovieBase, table=True):
    # require movies to be unique on release_date and title
    __table_args__ = (
        UniqueConstraint("release_date", "title", name="_release_date_title_uc"),
    )

    # note: sqlite will use the next largest available integer on inserts meaning that
    # primary keys can be re-used from previously deleted rows
    # https://sqlite.org/autoinc.html
    id: int | None = Field(default=None, primary_key=True)
    # CheckConstraint enforces at the database level:
    # https://docs.sqlalchemy.org/en/14/core/constraints.html#check-constraint
    release_date: date = Field(
        default=...,
        sa_column_args=[
            CheckConstraint(
                f"release_date > '{RELEASE_DATE_CONSTR.strftime('%Y-%m-%d')}'"
            )
        ],
        index=True,
    )
    created_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now())
    )
    # todo: cascade on delete (sa_relationship_kwargs)
    genres: list[Genre] = Relationship(
        back_populates="movies",
        link_model=GenreMovieLink,
        sa_relationship_kwargs={"lazy": "joined"},
    )
    # todo: created_by (user)


class MovieCreate(MovieBase):
    pass


class MovieResponse(MovieBase):
    id: int
    created_at: datetime
    updated_at: datetime | None
    genres: list[Genre] = []


class MovieUpdate(MovieBase):
    """used when updating movie data

    convenient to use this model, even though we accept Form data"""

    title: str | None = None
    release_date: date | None = Field(default=None)
    adult: bool | None = None
