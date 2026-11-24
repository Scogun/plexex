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
    """Capabilities available for a Plex account."""

    username: str | None
    plex_pass_active: bool
    subscription_plan: str | None
    subscription_features: tuple[str, ...]