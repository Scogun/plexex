"""PlexEx event entities."""
from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import get_plex_entry
from .const import DOMAIN, EVENT_FINAL_CREDITS_STARTED

EVENT_TYPE_FINAL_CREDITS_STARTED = "final_credits_started"
EVENT_DOMAIN = "event"
MEDIA_PLAYER_DOMAIN = "media_player"


def _server_unique_id(entry: ConfigEntry) -> str:
    """Return the unique ID of the server-wide event entity."""
    return f"{entry.entry_id}_playback_event"


def _player_unique_id(entry: ConfigEntry, player: entity_registry.RegistryEntry) -> str:
    """Return the unique ID of the event entity of one Plex media player."""
    return f"{entry.entry_id}_{player.unique_id}_playback_event"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the server-wide and the per-player playback event entities."""
    async_add_entities([PlexPlaybackEvent(entry)])

    plex_entry = get_plex_entry(hass, entry)
    if plex_entry is None:
        return

    registry = entity_registry.async_get(hass)
    added: set[str] = set()

    @callback
    def async_sync_players() -> None:
        """Keep exactly one event entity for each Plex media player."""
        players = {
            _player_unique_id(entry, player): player
            for player in entity_registry.async_entries_for_config_entry(
                registry, plex_entry.entry_id
            )
            if player.domain == MEDIA_PLAYER_DOMAIN
        }

        # Drop entities of players the official Plex integration removed.
        expected = {_server_unique_id(entry), *players}
        for entity in entity_registry.async_entries_for_config_entry(registry, entry.entry_id):
            if entity.domain == EVENT_DOMAIN and entity.unique_id not in expected:
                registry.async_remove(entity.entity_id)
        added.intersection_update(players)

        new_entities = [
            PlexPlayerPlaybackEvent(hass, entry, player)
            for unique_id, player in players.items()
            if unique_id not in added
        ]
        added.update(players)
        if new_entities:
            async_add_entities(new_entities)

    @callback
    def async_is_player_added_or_removed(
        event_data: entity_registry.EventEntityRegistryUpdatedData,
    ) -> bool:
        """Match media players entering or leaving the entity registry."""
        return event_data["action"] != "update" and event_data[
            "entity_id"
        ].startswith(f"{MEDIA_PLAYER_DOMAIN}.")

    @callback
    def async_registry_updated(
        event: Event[entity_registry.EventEntityRegistryUpdatedData],
    ) -> None:
        """Follow the media players of the official Plex integration."""
        # Removing a Plex device queues further registry events for the same
        # entities. Let Home Assistant handle those before touching the
        # registry again.
        hass.loop.call_soon(async_sync_settled)

    @callback
    def async_sync_settled() -> None:
        """Sync the players unless PlexEx was unloaded in the meantime."""
        if entry.state is ConfigEntryState.LOADED:
            async_sync_players()

    entry.async_on_unload(
        hass.bus.async_listen(
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED,
            async_registry_updated,
            event_filter=async_is_player_added_or_removed,
        )
    )
    async_sync_players()


def _server_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Describe the PlexEx device of a Plex server."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Plex",
        model="Plex Media Server",
    )


class PlexPlaybackEvent(EventEntity):
    """Expose playback markers of every player of a Plex server."""

    _attr_has_entity_name = True
    _attr_name = "Playback event"
    _attr_icon = "mdi:movie-play"
    _attr_event_types = [EVENT_TYPE_FINAL_CREDITS_STARTED]

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the event entity."""
        self._entry_id = entry.entry_id
        self._attr_unique_id = _server_unique_id(entry)
        self._attr_device_info = _server_device_info(entry)

    async def async_added_to_hass(self) -> None:
        """Listen for final credits events from this PlexEx server."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(
                EVENT_FINAL_CREDITS_STARTED,
                self._handle_final_credits_started,
            )
        )

    def _matches(self, event: Event) -> bool:
        """Return whether a playback event belongs to this entity."""
        return event.data.get("server") == self._entry_id

    @callback
    def _handle_final_credits_started(self, event: Event) -> None:
        """Publish matching playback events to Home Assistant."""
        if not self._matches(event):
            return

        self._trigger_event(
            EVENT_TYPE_FINAL_CREDITS_STARTED,
            {key: value for key, value in event.data.items() if key != "server"},
        )
        self.async_write_ha_state()


class PlexPlayerPlaybackEvent(PlexPlaybackEvent):
    """Expose playback markers of one Plex media player."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, player: entity_registry.RegistryEntry
    ) -> None:
        """Initialize the event entity of a Plex media player."""
        self._entry_id = entry.entry_id
        # The registry ID survives a rename of the media player entity.
        self._player_id = player.id
        self._attr_unique_id = _player_unique_id(entry, player)

        device = (
            device_registry.async_get(hass).async_get(player.device_id)
            if player.device_id
            else None
        )
        if (
            device is not None
            and getattr(device, "entry_type", None)
            is not device_registry.DeviceEntryType.SERVICE
        ):
            # Join the device the official Plex integration made for the player.
            self.device_entry = device
        else:
            # Web and other transient players share one service device, so
            # keep them apart by name on the PlexEx server device instead.
            name = player.name or player.original_name or player.entity_id
            self._attr_name = f"{name} playback event"
            self._attr_device_info = _server_device_info(entry)

    def _matches(self, event: Event) -> bool:
        """Return whether a playback event came from this media player."""
        if not super()._matches(event):
            return False
        player_entity_id = event.data.get("player_id")
        if player_entity_id is None:
            return False
        player = entity_registry.async_get(self.hass).async_get(player_entity_id)
        return player is not None and player.id == self._player_id
