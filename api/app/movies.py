import asyncio

from fastapi import APIRouter, Body, Depends, Query
from loguru import logger
from sqlalchemy.future import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import db
from app.config import Settings, get_settings
from app.db_helpers import commit, get_object_or_404, get_or_create
from app.tables import Genre, Movie, MovieCreate, MovieResponse, MovieUpdate
from app.tmdb import TMDBMovieResult, TMDBSearchResult, get_movie_data, tmdb_search

router = APIRouter()


@router.get("/search_movies/", response_model=list[TMDBSearchResult])
async def search_movies(
    query: str = Query(..., description="Percent encoded query"),
    year: int | None = Query(None),
    page: int = 1,
    settings: Settings = Depends(get_settings),
):

    params = {
        "api_key": settings.tmdb_api_key,
        "query": query,
        "include_adult": False,
        "page": page,
    }
    if year is not None:
        params["year"] = year

    return await tmdb_search(params, settings.tmdb_api_url)


async def create_movie_from_tmdb(
    tmdb_movie_result: tuple[TMDBMovieResult, str | None, list[str]],
    session: AsyncSession,
) -> Movie:

    movie_data, rating, genres = tmdb_movie_result

    # create movie instance from tmdb response data
    db_movie = Movie(rating=rating, **movie_data.dict())

    # adding genres to movie
    db_genres = [await get_or_create(session, Genre, name=genre) for genre in genres]

    db_movie.genres = db_genres

    session.add(db_movie)
    await commit(session)
    await session.refresh(db_movie)

    logger.info("Created movie: {}", db_movie.dict())

    return db_movie


@router.post("/tmdb_movie/", response_model=dict[str, MovieResponse])
async def create_movie_from_tmdb_id_endpoint(
    tmdb_ids: list[int] = Body(
        [], embed=True, description="List of tmdb movie ids to create"
    ),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(db.get_session),
) -> dict[int, Movie]:
    """Create Movie by passing in tmdb id

    If movie already exists, it doesn't create and returns data for that tmdb_id

    Accepts a list of tmdb_ids

    Returns a dict of {tmdb_id: MovieData}
    """

    # Was initially tempted to group all the work for each movie in a coroutine,
    # and then run all the requested tmdb_ids simultaneously using asyncio.gather
    # however, that did not work, because:
    # 1. movies in the database share genres (and eventually other models as well)
    # 2. if running with asyncio.gather, each task needs it's own database session
    # Some discussion here:
    # https://github.com/sqlalchemy/sqlalchemy/discussions/8554#discussioncomment-3700871

    tmdb_ids_uniq = set(tmdb_ids)

    # get movies that have matching tmdb id's from our database
    stmt = select(Movie).filter(Movie.tmdb_id.in_(tmdb_ids_uniq))
    existing_movies: list[Movie] = (await session.scalars(stmt)).unique().all()

    # determine which tmdb's remain to be created
    tmdb_ids_to_create = tmdb_ids_uniq - set([m.tmdb_id for m in existing_movies])

    # get the tmdb data for the tmdb_ids_to_create
    coros = [
        get_movie_data(tmdb_id, settings.tmdb_api_url, settings.tmdb_api_key)
        for tmdb_id in tmdb_ids_to_create
    ]
    tmdb_movie_results = await asyncio.gather(*coros)

    # create the entries in the database, serially
    db_movies = [
        await create_movie_from_tmdb(tmdb_movie_result, session)
        for tmdb_movie_result in tmdb_movie_results
    ]

    requested_movies = existing_movies + db_movies
    db_tmdb_ids = [m.tmdb_id for m in requested_movies]

    return {
        tmdb_id: requested_movies[db_tmdb_ids.index(tmdb_id)] for tmdb_id in tmdb_ids
    }


# todo: admin only?
@router.post("/movie/", response_model=MovieResponse)
async def create_movie(
    movie: MovieCreate,
    genres: list[str] = Body(default=[]),
    session: AsyncSession = Depends(db.get_session),
) -> Movie:
    """Create a movie by passing params

    Note: we will also support creating movies by passing a TMDB id
    """

    db_movie = Movie.from_orm(movie)

    # adding genres to movie
    db_genres = []
    for genre in genres:
        db_genres.append(await get_or_create(session, Genre, name=genre))
    db_movie.genres = db_genres

    session.add(db_movie)
    await commit(session)
    await session.refresh(db_movie)

    logger.info("Created movie: {}", db_movie.dict())

    return db_movie


@router.get("/movies/", response_model=list[MovieResponse])
async def list_movies(
    session: AsyncSession = Depends(db.get_session),
) -> list[Movie]:
    movies = (await session.execute(select(Movie))).scalars().unique().all()
    return movies


@router.get("/movie/{movie_id}", response_model=MovieResponse)
async def read_movie(
    movie_id: int, session: AsyncSession = Depends(db.get_session)
) -> Movie:
    movie = await get_object_or_404(session, Movie, movie_id)
    return movie


# todo: admin only?
@router.patch("/movie/{movie_id}", response_model=MovieResponse)
async def update_movie(
    movie_id: int,
    movie: MovieUpdate | None = None,
    genres: list[str] | None = Body(default=None),
    session: AsyncSession = Depends(db.get_session),
) -> Movie:

    db_movie = await get_object_or_404(session, Movie, movie_id)

    if movie:
        movie_data = movie.dict(exclude_defaults=True)
        for key, value in movie_data.items():
            setattr(db_movie, key, value)

    # adding genres to movie
    if genres is not None:
        db_genres = []
        for genre in genres:
            db_genres.append(await get_or_create(session, Genre, name=genre))
        db_movie.genres = db_genres

    # best attempt at not updating the movie if no data is actually passed in
    if movie or genres is not None:
        session.add(db_movie)
        await commit(session)
        await session.refresh(db_movie)

        logger.info("Updated movie: {}", db_movie.dict())
    return db_movie


@router.delete("/movie/{movie_id}")
async def delete_movie(
    movie_id: int, session: AsyncSession = Depends(db.get_session)
) -> dict[str, bool]:
    movie = await get_object_or_404(session, Movie, movie_id)
    await session.delete(movie)
    await commit(session)

    logger.info("Deleted movie: {}", movie.dict())
    return {"ok": True}
