"""PlexEx custom integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import create_coordinator
from .playback import PlexPlaybackMonitor
from .services import async_register_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.EVENT]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up PlexEx services."""
    async_register_services(hass)
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
) -> bool:
    """Set up PlexEx config entry."""
    try:
        coordinator_instance = create_coordinator(hass, entry)
    except HomeAssistantError as err:
        # The linked Plex server may be added back to the official Plex
        # integration later, so keep retrying instead of failing for good.
        raise ConfigEntryNotReady(str(err)) from err

    # Do not fail integration setup if Plex account lookup is temporarily
    # unavailable. The sensor will be created as unavailable and retried.
    await coordinator_instance.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator_instance

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )
    PlexPlaybackMonitor(hass, entry).start()

    return True


async def async_unload_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
) -> bool:
    """Unload PlexEx config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
