"""PlexEx data models."""
from dataclasses import dataclass

from .const import MARKER_KIND_FINAL_CREDITS, MARKER_TYPE_CREDITS


@dataclass(frozen=True)
class PlexConnection:
    """Connection settings taken from the official Plex config entry."""

    url: str
    token: str | None
    verify_ssl: bool = True


@dataclass(frozen=True)
class PlexCapabilities:
    """Plex Pass status of a server and details of its Plex account."""

    username: str | None
    plex_pass_active: bool | None
    subscription_plan: str | None
    subscription_features: tuple[str, ...]


@dataclass(frozen=True)
class Marker:
    """One Plex marker of a movie or an episode. Offsets are milliseconds."""

    type: str
    final: bool
    start: int
    end: int

    @property
    def kind(self) -> str:
        """Return the marker type, telling final credits from other credits."""
        if self.type == MARKER_TYPE_CREDITS and self.final:
            return MARKER_KIND_FINAL_CREDITS
        return self.type


@dataclass(frozen=True)
class MediaMarkers:
    """Markers of a movie or an episode, with the metadata events report."""

    rating_key: int
    media_type: str
    title: str
    show_title: str | None
    season: int | None
    episode: int | None
    markers: tuple[Marker, ...]
