"""Synchronous PlexAPI operations."""
import logging
from typing import Any
from plexapi.exceptions import PlexApiException
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from requests import RequestException, Session

from .models import PlexCapabilities, PlexConnection

_LOGGER = logging.getLogger(__name__)


def _connect(connection: PlexConnection) -> PlexServer:
    """Connect to the Plex server the same way the official integration does.

    Certificate verification is only disabled when the official Plex entry
    was configured with ``verify_ssl`` turned off.
    """
    session = None
    if connection.url.startswith("https") and not connection.verify_ssl:
        session = Session()
        session.verify = False
    return PlexServer(connection.url, connection.token, session)


def get_capabilities(connection: PlexConnection) -> PlexCapabilities:
    """Retrieve Plex Pass status from the server and details from plex.tv."""
    plex = _connect(connection)

    username = None
    subscription_plan = None
    features = []

    if connection.token is not None:
        try:
            account = MyPlexAccount(token=connection.token)
            username = getattr(account, "username", None)
            subscription_plan = getattr(account, "subscriptionPlan", None)
            features = getattr(account, "subscriptionFeatures", None) or []
        except (PlexApiException, RequestException) as err:
            _LOGGER.debug(
                "Plex account details are not available (%s)",
                type(err).__name__,
            )

    if isinstance(features, str):
        features = [features]

    return PlexCapabilities(
        username=username,
        plex_pass_active=getattr(plex, "myPlexSubscription", None),
        subscription_plan=subscription_plan,
        subscription_features=tuple(str(item) for item in features),
    )

def search_movies(connection: PlexConnection, title: str) -> dict[str, Any]:
    """Search the Plex movie library."""
    plex = _connect(connection)
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

def mark_unwatched(connection: PlexConnection, rating_key: int) -> None:
    """Mark a Plex library item as unwatched."""
    plex = _connect(connection)
    plex.fetchItem(rating_key).markUnwatched()
