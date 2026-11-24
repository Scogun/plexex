"""Shared Plex connection helpers."""
from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN, PLEX_DOMAIN
from .models import PlexConnection

def _get_plex_entry(
        hass: HomeAssistant, plexex_entry: ConfigEntry
) -> ConfigEntry | None:
    """Return the official Plex entry a PlexEx entry is linked to, if any."""
    server_id = plexex_entry.unique_id
    if server_id is None:
        return None
    plex_entry = hass.config_entries.async_entry_for_domain_unique_id(
        PLEX_DOMAIN, server_id
    )
    if plex_entry is None or plex_entry.source == SOURCE_IGNORE:
        return None
    return plex_entry


def resolve_plex_connection(
        hass: HomeAssistant, plexex_entry_id: str | None
) -> PlexConnection:
    """Resolve a PlexEx config entry ID to its official Plex connection.

    If no ID is supplied, use the only configured PlexEx entry. An explicit ID
    is required when multiple PlexEx entries are configured.
    """
    plexex_entries = hass.config_entries.async_entries(DOMAIN)

    if plexex_entry_id:
        connections = [
            entry for entry in plexex_entries
            if entry.entry_id == plexex_entry_id
        ]
    else:
        # Without an explicit ID, ignore entries whose Plex entry is gone.
        connections = [
            entry for entry in plexex_entries
            if _get_plex_entry(hass, entry) is not None
        ]
        if len(connections) > 1:
            raise ServiceValidationError(
                "More than one PlexEx connection is configured. Specify 'server'."
            )

    if not connections:
        raise ServiceValidationError(
            "No matching PlexEx connection is configured. Add PlexEx and select "
            "an existing official Plex integration entry."
        )

    plex_entry = _get_plex_entry(hass, connections[0])
    if plex_entry is None:
        raise ServiceValidationError(
            "The Plex server linked to this PlexEx connection is not configured "
            "in the official Plex integration. Add the server there, or remove "
            "this PlexEx entry and add it again."
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
