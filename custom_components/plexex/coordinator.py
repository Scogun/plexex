
"""Plex server capabilities coordinator."""
from __future__ import annotations
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .common import resolve_plex_connection
from .const import DOMAIN
from .models import PlexCapabilities
from .plex_client import get_capabilities

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=1)


class PlexCapabilitiesCoordinator(
    DataUpdateCoordinator[PlexCapabilities]
):
    """Fetch and cache Plex Pass status and account details."""

    def __init__(
            self,
            hass: HomeAssistant,
            entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self._entry_id = entry.entry_id

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}_capabilities",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> PlexCapabilities:
        """Fetch Plex Pass status and account details."""
        try:
            connection = resolve_plex_connection(self.hass, self._entry_id)

            return await self.hass.async_add_executor_job(
                get_capabilities,
                connection,
            )
        except Exception as err:
            raise UpdateFailed(
                f"Could not retrieve Plex Pass status: {err}"
            ) from err


def create_coordinator(
        hass: HomeAssistant,
        entry: ConfigEntry,
) -> PlexCapabilitiesCoordinator:
    """Create a coordinator using the official Plex connection."""
    resolve_plex_connection(hass, entry.entry_id)

    return PlexCapabilitiesCoordinator(hass, entry)
