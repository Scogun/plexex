"""PlexEx custom integration."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN
from .services import async_register_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

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