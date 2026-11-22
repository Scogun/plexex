"""Synchronous PlexAPI operations."""
from typing import Any
from plexapi.server import PlexServer

def search_movies(url: str, token: str, title: str) -> dict[str, Any]:
    """Search the Plex movie library."""
    plex = PlexServer(url, token)
    found_movies = plex.library.search(title=title, libtype="movie")
    movies = []
    for movie in found_movies:
        last_viewed_at = movie.lastViewedAt
        movies.append({
            "ratingKey": str(movie.ratingKey),
            "title": movie.title,
            "year": movie.year,
            "viewCount": movie.viewCount or 0,
            "lastViewedAt": (
                last_viewed_at.isoformat() if last_viewed_at is not None else None
            ),
        })
    return {"movies": movies}

def mark_unwatched(url: str, token: str, rating_key: str) -> None:
    """Mark a Plex library item as unwatched."""
    plex = PlexServer(url, token)
    plex.fetchItem(rating_key).markUnwatched()
