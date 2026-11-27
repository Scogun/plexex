"""Synchronous PlexAPI operations."""
import logging
from typing import Any
from plexapi.exceptions import PlexApiException
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from requests import RequestException, Session

from .const import MARKER_TYPES
from .models import Marker, MediaMarkers, PlexCapabilities, PlexConnection

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

def search(connection: PlexConnection, media_type: str, title: str) -> dict[str, Any]:
    """Search the Plex library for items of one type by their title."""
    plex = _connect(connection)
    items = []
    for item in plex.library.search(title=title, libtype=media_type):
        last_viewed_at = item.lastViewedAt
        found = {
            "type": item.type,
            "ratingKey": int(item.ratingKey),
            "title": item.title,
            "year": item.year,
            "viewCount": item.viewCount or 0,
            "lastViewedAt": (
                last_viewed_at.isoformat() if last_viewed_at is not None else None
            ),
        }
        if item.type == "season":
            found["showTitle"] = item.parentTitle
            found["seasonNumber"] = item.index
        elif item.type == "episode":
            found["showTitle"] = item.grandparentTitle
            found["seasonNumber"] = item.parentIndex
            found["episodeNumber"] = item.index
        items.append(found)
    return {"items": items}

def mark_unwatched(connection: PlexConnection, rating_key: int) -> None:
    """Mark a Plex library item as unwatched."""
    plex = _connect(connection)
    plex.fetchItem(rating_key).markUnwatched()

def get_markers(connection: PlexConnection, rating_key: int) -> MediaMarkers | None:
    """Fetch the markers of a movie or an episode with cacheable metadata."""
    plex = _connect(connection)
    item = plex.fetchItem(rating_key)
    if item.type not in ("movie", "episode"):
        return None
    item.reload(includeMarkers=True)

    is_episode = item.type == "episode"
    markers = (
        Marker(
            type=marker.type,
            final=bool(marker.final),
            start=int(marker.start),
            end=int(marker.end),
        )
        for marker in item.markers
        if marker.type in MARKER_TYPES
        and marker.start is not None
        and marker.end is not None
    )
    return MediaMarkers(
        rating_key=int(item.ratingKey),
        media_type=item.type,
        title=item.title,
        show_title=item.grandparentTitle if is_episode else None,
        season=item.parentIndex if is_episode else None,
        episode=item.index if is_episode else None,
        markers=tuple(sorted(markers, key=lambda marker: marker.start)),
    )
