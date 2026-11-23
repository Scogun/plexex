
"""PlexEx binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlexCapabilitiesCoordinator


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities,
) -> None:
    """Set up PlexEx binary sensors."""
    coordinator: PlexCapabilitiesCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        PlexPassBinarySensor(coordinator, entry),
    ])


class PlexPassBinarySensor(
    CoordinatorEntity[PlexCapabilitiesCoordinator],
    BinarySensorEntity,
):
    """Represent Plex Pass subscription status."""

    _attr_has_entity_name = True
    _attr_name = "Plex Pass"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:account-check"

    def __init__(
            self,
            coordinator: PlexCapabilitiesCoordinator,
            entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.entry_id}_plex_pass"
        self._attr_entity_registry_enabled_default = bool(coordinator.token)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Plex",
            model="Plex Media Server",
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether Plex Pass is active."""
        if self.coordinator.data is None:
            return None

        return self.coordinator.data.plex_pass_active

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return Plex account details."""
        data = self.coordinator.data

        if data is None:
            return {}

        return {
            "username": data.username,
            "subscription_plan": data.subscription_plan,
            "subscription_features": list(data.subscription_features),
        }
