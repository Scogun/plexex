"""PlexEx service actions."""
import logging
from typing import Any
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from .common import resolve_plex_connection
from .const import (
    CONF_SERVER, DOMAIN, MARKER_KINDS, SEARCH_TYPES,
    SERVICE_MARK_UNWATCHED, SERVICE_SEARCH, SERVICE_SEARCH_MOVIES,
    SERVICE_SKIP_MARKER,
)
from .plex_client import mark_unwatched, search

_LOGGER = logging.getLogger(__name__)

SEARCH_SCHEMA = vol.Schema({
    vol.Required("type"): vol.In(SEARCH_TYPES),
    vol.Required("title"): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional(CONF_SERVER): cv.string,
})
SEARCH_MOVIES_SCHEMA = vol.Schema({
    vol.Required("title"): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional(CONF_SERVER): cv.string,
})
MARK_UNWATCHED_SCHEMA = vol.Schema({
    vol.Required("rating_key"): cv.positive_int,
    vol.Optional(CONF_SERVER): cv.string,
})
SKIP_MARKER_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Optional("markers", default=[]): vol.All(
        cv.ensure_list, [vol.In(MARKER_KINDS)]
    ),
})

def async_register_services(hass: HomeAssistant) -> None:
    """Register PlexEx actions."""
    async def handle_search(call: ServiceCall) -> dict[str, Any]:
        media_type = call.data["type"]
        title = call.data["title"].strip()
        if not title:
            raise ServiceValidationError(f"The {media_type} title cannot be empty.")
        connection = resolve_plex_connection(hass, call.data.get(CONF_SERVER))
        try:
            return await hass.async_add_executor_job(
                search, connection, media_type, title
            )
        except Exception as err:
            _LOGGER.error("PlexEx %s search failed (%s)", media_type, type(err).__name__)
            raise HomeAssistantError(
                f"Plex {media_type} search failed ({type(err).__name__})."
            ) from err

    # Deprecated: use plexex.search with type "movie". Remove in 0.10.0.
    async def handle_search_movies(call: ServiceCall) -> dict[str, Any]:
        _LOGGER.warning(
            "The plexex.search_movies action is deprecated and will be removed in "
            "PlexEx 0.10.0. Use plexex.search with type 'movie' instead"
        )
        # The data of a call is read-only, so search with a copy that names the type.
        result = await handle_search(
            ServiceCall(
                hass,
                DOMAIN,
                SERVICE_SEARCH,
                {**call.data, "type": "movie"},
                call.context,
                call.return_response,
            )
        )
        return {"movies": result["items"]}

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

    async def handle_skip_marker(call: ServiceCall) -> None:
        entity_id = call.data["entity_id"]
        kinds = call.data["markers"]
        # A media player belongs to one server, so at most one monitor knows it.
        marker = next(
            (
                marker
                for entry in hass.config_entries.async_loaded_entries(DOMAIN)
                if (
                    marker := entry.runtime_data.async_get_current_marker(
                        entity_id, kinds
                    )
                )
            ),
            None,
        )
        if marker is None:
            raise ServiceValidationError(
                f"{entity_id} is not playing inside "
                f"{'one of the selected markers' if kinds else 'a marker'}."
            )
        # The official Plex integration owns the player, so let it seek.
        await hass.services.async_call(
            "media_player",
            "media_seek",
            {"entity_id": entity_id, "seek_position": marker.end / 1000},
            blocking=True,
            context=call.context,
        )

    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH, handle_search,
        schema=SEARCH_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH_MOVIES, handle_search_movies,
        schema=SEARCH_MOVIES_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MARK_UNWATCHED, handle_mark_unwatched,
        schema=MARK_UNWATCHED_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SKIP_MARKER, handle_skip_marker,
        schema=SKIP_MARKER_SCHEMA,
    )
