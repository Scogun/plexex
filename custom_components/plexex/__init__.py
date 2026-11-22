"""PlexEx custom integration."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .services import async_register_services

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up PlexEx services."""
    async_register_services(hass)
    return True

async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
) -> bool:
    """Set up PlexEx config entry."""
    return True


async def async_unload_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
) -> bool:
    """Unload PlexEx config entry."""
    return True