"""PlexEx data models."""
from dataclasses import dataclass


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