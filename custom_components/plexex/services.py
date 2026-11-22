"""PlexEx service actions."""
import logging
from typing import Any
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from .const import (
    CONF_PLEX_ENTRY_ID, CONF_SERVER, DOMAIN,
    SERVICE_MARK_UNWATCHED, SERVICE_SEARCH_MOVIES,
)
from .plex_client import mark_unwatched, search_movies

_LOGGER = logging.getLogger(__name__)

SEARCH_MOVIES_SCHEMA = vol.Schema({
    vol.Required("title"): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional(CONF_SERVER): cv.string,
})
MARK_UNWATCHED_SCHEMA = vol.Schema({
    vol.Required("rating_key"): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional(CONF_SERVER): cv.string,
})

def _resolve_plex_connection(
        hass: HomeAssistant, server_name: str | None
) -> tuple[str, str]:
    """Resolve an official Plex entry to its URL and token."""
    matches: list[tuple[str, ConfigEntry]] = []
    for plexex_entry in hass.config_entries.async_entries(DOMAIN):
        plex_entry_id = plexex_entry.data.get(CONF_PLEX_ENTRY_ID)
        plex_entry = hass.config_entries.async_get_entry(plex_entry_id)
        if plex_entry is None or plex_entry.domain != "plex":
            continue
        display_name = str(
            plex_entry.data.get("server") or plex_entry.title or plex_entry.entry_id
        )
        matches.append((display_name, plex_entry))

    if server_name:
        requested = server_name.casefold()
        matches = [
            item for item in matches
            if item[0].casefold() == requested or item[1].entry_id.casefold() == requested
        ]
    elif len(matches) > 1:
        raise ServiceValidationError(
            "More than one PlexEx server is configured. Specify the 'server' field."
        )

    if not matches:
        raise ServiceValidationError(
            "No matching PlexEx server is configured. Add PlexEx and select "
            "an existing official Plex integration entry."
        )

    plex_entry = matches[0][1]
    server_config = plex_entry.data.get("server_config") or {}
    url = server_config.get("url")
    token = server_config.get("token")
    if not url or not token:
        raise HomeAssistantError(
            "The selected official Plex entry has no URL/token in data.server_config."
        )
    return str(url), str(token)

def async_register_services(hass: HomeAssistant) -> None:
    """Register PlexEx actions."""
    async def handle_search_movies(call: ServiceCall) -> dict[str, Any]:
        title = call.data["title"].strip()
        if not title:
            raise ServiceValidationError("The movie title cannot be empty.")
        url, token = _resolve_plex_connection(hass, call.data.get(CONF_SERVER))
        try:
            return await hass.async_add_executor_job(search_movies, url, token, title)
        except Exception as err:
            _LOGGER.error("PlexEx movie search failed (%s)", type(err).__name__)
            raise HomeAssistantError(
                f"Plex movie search failed ({type(err).__name__})."
            ) from err

    async def handle_mark_unwatched(call: ServiceCall) -> None:
        rating_key = call.data["rating_key"]
        if not rating_key:
            raise ServiceValidationError("The rating_key cannot be empty.")
        url, token = _resolve_plex_connection(hass, call.data.get(CONF_SERVER))
        try:
            await hass.async_add_executor_job(mark_unwatched, url, token, rating_key)
        except Exception as err:
            _LOGGER.error("PlexEx mark_unwatched failed (%s)", type(err).__name__)
            raise HomeAssistantError(
                f"Could not mark Plex item as unwatched ({type(err).__name__})."
            ) from err

    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH_MOVIES, handle_search_movies,
        schema=SEARCH_MOVIES_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MARK_UNWATCHED, handle_mark_unwatched,
        schema=MARK_UNWATCHED_SCHEMA,
    )
