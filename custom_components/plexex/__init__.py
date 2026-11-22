"""PlexEx custom integration."""
from homeassistant.core import HomeAssistant
from .services import async_register_services

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up PlexEx services."""
    async_register_services(hass)
    return True
