"""PlexEx event entities."""
from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_FINAL_CREDITS_STARTED

EVENT_TYPE_FINAL_CREDITS_STARTED = "final_credits_started"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PlexEx playback event entity."""
    async_add_entities([PlexPlaybackEvent(entry)])


class PlexPlaybackEvent(EventEntity):
    """Expose Plex playback markers as a Home Assistant event entity."""

    _attr_has_entity_name = True
    _attr_name = "Playback event"
    _attr_icon = "mdi:movie-play"
    _attr_event_types = [EVENT_TYPE_FINAL_CREDITS_STARTED]

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the event entity."""
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_playback_event"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Plex",
            model="Plex Media Server",
        )

    async def async_added_to_hass(self) -> None:
        """Listen for final credits events from this PlexEx server."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(
                EVENT_FINAL_CREDITS_STARTED,
                self._handle_final_credits_started,
            )
        )

    @callback
    def _handle_final_credits_started(self, event: Event) -> None:
        """Publish matching playback events to Home Assistant."""
        if event.data.get("server") != self._entry_id:
            return

        self._trigger_event(
            EVENT_TYPE_FINAL_CREDITS_STARTED,
            {key: value for key, value in event.data.items() if key != "server"},
        )
        self.async_write_ha_state()
