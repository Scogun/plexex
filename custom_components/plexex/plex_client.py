"""Synchronous PlexAPI operations."""
from typing import Any
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from .models import PlexCapabilities

def get_account_capabilities(token: str | None) -> PlexCapabilities | None:
    """Retrieve Plex account subscription capabilities."""
    if token is None:
        return None

    account = MyPlexAccount(token=token)

    features = getattr(account, "subscriptionFeatures", None) or []

    if isinstance(features, str):
        features = [features]

    return PlexCapabilities(
        username=getattr(account, "username", None),
        plex_pass_active=bool(
            getattr(account, "subscriptionActive", False)
        ),
        subscription_plan=getattr(account, "subscriptionPlan", None),
        subscription_features=tuple(str(item) for item in features),
    )

def search_movies(url: str, token: str | None, title: str) -> dict[str, Any]:
    """Search the Plex movie library."""
    plex = PlexServer(url, token)
    found_movies = plex.library.search(title=title, libtype="movie")
    movies = []
    for movie in found_movies:
        last_viewed_at = movie.lastViewedAt
        movies.append({
            "ratingKey": int(movie.ratingKey),
            "title": movie.title,
            "year": movie.year,
            "viewCount": movie.viewCount or 0,
            "lastViewedAt": (
                last_viewed_at.isoformat() if last_viewed_at is not None else None
            ),
        })
    return {"movies": movies}

def mark_unwatched(url: str, token: str | None, rating_key: int) -> None:
    """Mark a Plex library item as unwatched."""
    plex = PlexServer(url, token)
    plex.fetchItem(rating_key).markUnwatched()
