"""Shared Plex connection helpers."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN, PLEX_DOMAIN
from .models import PlexConnection


def resolve_plex_connection(
        hass: HomeAssistant, plexex_entry_id: str | None
) -> PlexConnection:
    """Resolve a PlexEx config entry ID to its official Plex connection.

    If no ID is supplied, use the only configured PlexEx entry. An explicit ID
    is required when multiple PlexEx entries are configured.
    """
    connections: list[ConfigEntry] = []
    for plexex_entry in hass.config_entries.async_entries(DOMAIN):
        plex_entry_id = plexex_entry.unique_id
        if plex_entry_id is None:
            continue
        plex_entry = hass.config_entries.async_get_entry(plex_entry_id)
        if plex_entry is not None and plex_entry.domain == "plex":
            connections.append(plexex_entry)

    if plexex_entry_id:
        connections = [
            entry for entry in connections
            if entry.entry_id == plexex_entry_id
        ]
    elif len(connections) > 1:
        raise ServiceValidationError(
            "More than one PlexEx connection is configured. Specify 'server'."
        )

    if not connections:
        raise ServiceValidationError(
            "No matching PlexEx connection is configured. Add PlexEx and select "
            "an existing official Plex integration entry."
        )

    plex_entry_id = connections[0].unique_id
    if plex_entry_id is None:
        raise ServiceValidationError(
            "The selected PlexEx connection has no available official Plex entry."
        )
    plex_entry = hass.config_entries.async_get_entry(plex_entry_id)
    if plex_entry is None or plex_entry.domain != PLEX_DOMAIN:
        raise ServiceValidationError(
            "The selected PlexEx connection has no available official Plex entry."
        )

    server_config = plex_entry.data.get("server_config") or {}
    url = server_config.get("url")
    token = server_config.get("token")
    if not url:
        raise HomeAssistantError(
            "The selected official Plex entry has no URL in data.server_config."
        )

    return PlexConnection(
        url=str(url),
        token=str(token) if token is not None else None,
        # The official integration treats a missing value as "verify".
        verify_ssl=bool(server_config.get("verify_ssl", True)),
    )
