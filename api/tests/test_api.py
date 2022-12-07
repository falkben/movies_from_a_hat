from datetime import date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import config
from app.movies import TMDBSearchResult
from app.tables import Genre, Movie, MovieResponse

from .api_fixtures import client_fixture  # noqa: F401

DUDE_DATA = {
    "title": "The Big Lebowski",
    "release_date": date(1998, 3, 6).strftime("%Y-%m-%d"),
    "runtime": 117,
    "tmdb_id": 115,
    "imdb_id": "tt0118715",
    "poster": "/gocqX3Y5biEC9SezdqhTXVV2KeT.jpg",
    "rating": "R",
    "adult": False,
}
DUDE_GENRES_DATA = ["Comedy", "Crime"]


DIFF_DATE = date(1950, 1, 1).strftime("%Y-%m-%d")


@pytest.fixture
async def dude_movie(session: AsyncSession):
    movie = Movie(**DUDE_DATA)
    movie.genres = [Genre(name=g) for g in DUDE_GENRES_DATA]
    session.add(movie)
    await session.commit()
    await session.refresh(movie)
    yield movie


def test_create_movie(client: TestClient):
    # takes FORM data
    resp = client.post("/movie/", json={"movie": DUDE_DATA})
    data = resp.json()

    assert resp.status_code == 200, resp.json()
    assert data["id"] is not None
    assert data["title"] == DUDE_DATA["title"]
    assert data["release_date"] == DUDE_DATA["release_date"]
    assert data["runtime"] == DUDE_DATA["runtime"]
    assert datetime.fromisoformat(data["created_at"]) < datetime.utcnow()
    assert data["genres"] == []


async def test_create_movies_same_title_diff_year(
    client: TestClient, dude_movie: Movie
):

    resp = client.post(
        "/movie/", json={"movie": DUDE_DATA | {"release_date": DIFF_DATE}}
    )
    data = resp.json()

    assert resp.status_code == 200, resp.json()
    assert data["id"] is not None
    assert data["title"] == DUDE_DATA["title"]
    assert data["release_date"] == DIFF_DATE
    assert data["runtime"] == DUDE_DATA["runtime"]
    assert datetime.fromisoformat(data["created_at"]) < datetime.utcnow()
    assert data["genres"] == []


async def test_create_movies_same_title_same_year(
    client: TestClient, dude_movie: Movie
):
    """Movie title and year is unique"""

    resp = client.post("/movie/", json={"movie": DUDE_DATA})
    assert resp.status_code == 422


def test_create_movie_genres(client: TestClient):
    # takes FORM data
    resp = client.post(
        "/movie/", json={"movie": DUDE_DATA} | {"genres": DUDE_GENRES_DATA}
    )
    data = resp.json()

    assert resp.status_code == 200, resp.json()
    assert data["id"] is not None
    assert data["title"] == DUDE_DATA["title"]
    assert data["release_date"] == DUDE_DATA["release_date"]
    assert data["runtime"] == DUDE_DATA["runtime"]
    assert datetime.fromisoformat(data["created_at"]) < datetime.utcnow()
    assert [g["name"] for g in data["genres"]] == DUDE_GENRES_DATA


def test_create_movie_incomplete(client: TestClient):
    # no release_date
    resp = client.post("/movie/", json={"movie": {"title": "No release_date movie"}})
    assert resp.status_code == 422

    # no title
    resp = client.post("/movie/", json={"movie": {"release_date": DIFF_DATE}})
    assert resp.status_code == 422


def test_create_movie_invalid(client: TestClient):
    # release_date takes a formatted date, not a mapping/dict
    resp = client.post(
        "/movie/",
        json={
            "movie": {
                "title": "Bad release_date type",
                "release_date": {"release_date": "1998"},
            }
        },
    )
    assert resp.status_code == 422

    # bad release_date
    resp = client.post(
        "/movie/",
        json={
            "movie": {
                "title": "Bad release_date value",
                "release_date": "5555_three",
            }
        },
    )
    assert resp.status_code == 422


async def test_read_movie(client: TestClient, dude_movie: Movie):

    resp = client.get(f"/movie/{dude_movie.id}")
    data = resp.json()

    assert resp.status_code == 200
    assert data["title"] == DUDE_DATA["title"]
    assert data["release_date"] == DUDE_DATA["release_date"]
    assert data["runtime"] == DUDE_DATA["runtime"]
    assert datetime.fromisoformat(data["created_at"]) < datetime.utcnow()
    assert data["updated_at"] is None


async def test_update_movie(client: TestClient, dude_movie: Movie):
    resp = client.patch(
        f"/movie/{dude_movie.id}", json={"movie": {"title": "The Dude"}}
    )
    data = resp.json()

    assert resp.status_code == 200, data
    assert data["title"] == "The Dude"
    assert data["runtime"] == DUDE_DATA["runtime"]
    assert data["id"] == dude_movie.id
    assert data["updated_at"] is not None

    # update the genres
    resp = client.patch(f"/movie/{dude_movie.id}", json={"genres": ["90s"]})
    assert resp.status_code == 200, resp.json()
    assert [g["name"] for g in resp.json()["genres"]] == ["90s"]

    # update genres with same data (instead of creating new objects we "get" existing instance)
    resp = client.patch(f"/movie/{dude_movie.id}", json={"genres": ["90s"]})
    assert resp.status_code == 200, resp.json()
    assert [g["name"] for g in resp.json()["genres"]] == ["90s"]


async def test_update_movie_no_change(client: TestClient, dude_movie: Movie):
    """Verify that we don't update the movie if no data is patched"""
    resp = client.patch(f"/movie/{dude_movie.id}", json={})

    data = resp.json()
    assert resp.status_code == 200, data

    movie_patch = MovieResponse(**data)
    assert movie_patch.created_at == dude_movie.created_at
    assert movie_patch.updated_at is None


async def test_remove_genres(client: TestClient, dude_movie: Movie):
    resp = client.patch(f"/movie/{dude_movie.id}", json={"genres": []})

    data = resp.json()
    assert resp.status_code == 200, data
    # check other data is still there
    movie_patch = MovieResponse(**data)
    assert movie_patch.title == dude_movie.title
    assert movie_patch.genres == []


async def test_delete_movie(
    session: AsyncSession, client: TestClient, dude_movie: Movie
):

    resp = client.delete(f"/movie/{dude_movie.id}")
    assert resp.status_code == 200

    movie_in_db = await session.get(Movie, dude_movie.id)
    assert movie_in_db is None


def test_search_movies(client: TestClient, mocked_TMDB, mocked_TMDB_config_req):
    resp = client.get("/search_movies/", params={"query": "big"})
    assert resp.status_code == 200, resp.json()
    for result_dict in resp.json():
        TMDBSearchResult.parse_obj(result_dict)


def test_search_movies_not_found(
    client: TestClient, respx_mock, mocked_TMDB_config_req
):
    tmdb_route = respx_mock.get(
        f"{config.TMDB_API_URL}/search/movie", name="search_tmdb_movies"
    )
    tmdb_route.return_value = httpx.Response(404)
    resp = client.get("/search_movies/", params={"query": "big"})
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Bad search params"}


def test_search_movies_tmdb_down(
    client: TestClient, respx_mock, mocked_TMDB_config_req
):
    tmdb_route = respx_mock.get(
        f"{config.TMDB_API_URL}/search/movie", name="search_tmdb_movies"
    )
    tmdb_route.return_value = httpx.Response(500)
    resp = client.get("/search_movies/", params={"query": "big"})
    assert resp.status_code == 504
    assert resp.json() == {"detail": "Gateway Timeout"}


def test_create_from_tmdb(
    client: TestClient, mocked_TMDB_movie_results, mocked_TMDB_config_req
):
    resp = client.post("/tmdb_movie", json={"tmdb_ids": [DUDE_DATA["tmdb_id"]]})
    assert resp.status_code == 200, resp.json()
    created_movie = resp.json()[str(DUDE_DATA["tmdb_id"])]
    assert created_movie["title"] == DUDE_DATA["title"]
    assert created_movie["runtime"] == DUDE_DATA["runtime"]
    assert created_movie["updated_at"] is None
    assert [g["name"] for g in created_movie["genres"]] == DUDE_GENRES_DATA


def test_create_mult_from_tmdb(
    client: TestClient, mocked_TMDB_movie_results, mocked_TMDB_config_req
):
    resp = client.post("/tmdb_movie", json={"tmdb_ids": [115, 550]})
    assert resp.status_code == 200, resp.json()

    resp_data = resp.json()
    assert len(resp_data) == 2


def test_create_mult_from_tmdb_order(
    client: TestClient, mocked_TMDB_movie_results, mocked_TMDB_config_req
):
    ids_sent = [115, 550]
    resp = client.post("/tmdb_movie", json={"tmdb_ids": ids_sent})
    assert resp.status_code == 200, resp.json()
    ids_returned = [m["tmdb_id"] for _, m in resp.json().items()]
    assert ids_returned == ids_sent

    ids_sent = [550, 6978, 115]
    resp = client.post("/tmdb_movie", json={"tmdb_ids": ids_sent})
    assert resp.status_code == 200, resp.json()
    ids_returned = [m["tmdb_id"] for _, m in resp.json().items()]
    assert ids_returned == ids_sent


def test_create_from_tmdb_empty(client: TestClient, mocked_TMDB_config_req):
    resp = client.post("/tmdb_movie", json={"tmdb_ids": []})
    assert resp.status_code == 200, resp.json()
    assert resp.json() == {}


def test_create_from_tmdb_not_found(
    client: TestClient, mocked_TMDB_movie_results, mocked_TMDB_config_req
):

    resp = client.post("/tmdb_movie", json={"tmdb_ids": [0]})
    assert resp.status_code == 404, resp.json()
