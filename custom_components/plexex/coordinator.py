
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
from .plex_client import get_account_capabilities

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=1)


class PlexCapabilitiesCoordinator(
    DataUpdateCoordinator[PlexCapabilities]
):
    """Fetch and cache Plex account capabilities."""

    def __init__(
            self,
            hass: HomeAssistant,
            entry: ConfigEntry,
            token: str | None,
    ) -> None:
        """Initialize the coordinator."""
        self.token = token

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}_capabilities",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> PlexCapabilities | None:
        """Fetch account capabilities from Plex."""
        try:
            return await self.hass.async_add_executor_job(
                get_account_capabilities,
                self.token,
            )
        except Exception as err:
            raise UpdateFailed(
                f"Could not retrieve Plex account capabilities: {err}"
            ) from err


def create_coordinator(
        hass: HomeAssistant,
        entry: ConfigEntry,
) -> PlexCapabilitiesCoordinator:
    """Create a coordinator using the official Plex connection."""
    _, token = resolve_plex_connection(hass, entry.entry_id)

    return PlexCapabilitiesCoordinator(hass, entry, token)
