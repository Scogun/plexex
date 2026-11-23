"""Shared Plex connection helpers."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import CONF_PLEX_ENTRY_ID, DOMAIN


def resolve_plex_connection(
        hass: HomeAssistant, plexex_entry_id: str | None
) -> tuple[str, str]:
    """Resolve a PlexEx config entry ID to its official Plex URL and token.

    If no ID is supplied, use the only configured PlexEx entry. An explicit ID
    is required when multiple PlexEx entries are configured.
    """
    connections: list[ConfigEntry] = []
    for plexex_entry in hass.config_entries.async_entries(DOMAIN):
        plex_entry_id = plexex_entry.data.get(CONF_PLEX_ENTRY_ID)
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

    plex_entry_id = connections[0].data.get(CONF_PLEX_ENTRY_ID)
    plex_entry = hass.config_entries.async_get_entry(plex_entry_id)
    if plex_entry is None or plex_entry.domain != "plex":
        raise ServiceValidationError(
            "The selected PlexEx connection has no available official Plex entry."
        )

    server_config = plex_entry.data.get("server_config") or {}
    url = server_config.get("url")
    token = server_config.get("token")
    if not url or not token:
        raise HomeAssistantError(
            "The selected official Plex entry has no URL/token in data.server_config."
        )

    return str(url), str(token)
