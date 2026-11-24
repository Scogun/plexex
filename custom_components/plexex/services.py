"""PlexEx service actions."""
import logging
from typing import Any
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from .common import resolve_plex_connection
from .const import (
    CONF_SERVER, DOMAIN,
    SERVICE_MARK_UNWATCHED, SERVICE_SEARCH_MOVIES,
)
from .plex_client import mark_unwatched, search_movies

_LOGGER = logging.getLogger(__name__)

SEARCH_MOVIES_SCHEMA = vol.Schema({
    vol.Required("title"): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional(CONF_SERVER): cv.string,
})
MARK_UNWATCHED_SCHEMA = vol.Schema({
    vol.Required("rating_key"): cv.positive_int,
    vol.Optional(CONF_SERVER): cv.string,
})

def async_register_services(hass: HomeAssistant) -> None:
    """Register PlexEx actions."""
    async def handle_search_movies(call: ServiceCall) -> dict[str, Any]:
        title = call.data["title"].strip()
        if not title:
            raise ServiceValidationError("The movie title cannot be empty.")
        connection = resolve_plex_connection(hass, call.data.get(CONF_SERVER))
        try:
            return await hass.async_add_executor_job(search_movies, connection, title)
        except Exception as err:
            _LOGGER.error("PlexEx movie search failed (%s)", type(err).__name__)
            raise HomeAssistantError(
                f"Plex movie search failed ({type(err).__name__})."
            ) from err

    async def handle_mark_unwatched(call: ServiceCall) -> None:
        rating_key = call.data["rating_key"]
        if not rating_key:
            raise ServiceValidationError("The rating_key cannot be empty.")
        connection = resolve_plex_connection(hass, call.data.get(CONF_SERVER))
        try:
            await hass.async_add_executor_job(mark_unwatched, connection, rating_key)
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
