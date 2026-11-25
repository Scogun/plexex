"""Monitor Plex integration media-player updates for final credits."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .common import resolve_plex_connection
from .const import EVENT_FINAL_CREDITS_STARTED, PLEX_DOMAIN
from .plex_client import get_final_credits_marker

_LOGGER = logging.getLogger(__name__)
MARKER_CACHE_SIZE = 256
POSITION_CHECK_INTERVAL = timedelta(seconds=1)


@dataclass
class Playback:
    """Latest playback position reported for one Plex media player."""

    rating_key: int
    playing: bool
    position: float
    updated_at: datetime
    user: str | None
    player_name: str | None
    checked_position: float = 0.0

    def position_at(self, now: datetime) -> float:
        """Estimate the position from the latest Plex position update."""
        if not self.playing:
            return self.position
        return self.position + max(0.0, (now - self.updated_at).total_seconds())


class PlexPlaybackMonitor:
    """Use Plex media-player state updates, without polling Plex sessions."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the monitor for one linked Plex server."""
        self.hass = hass
        self._entry = entry
        self._plex_entry_id: str | None = None
        self._playbacks: dict[str, Playback] = {}
        self._markers: OrderedDict[int, dict | None] = OrderedDict()

    def start(self) -> None:
        """Listen for state updates pushed by Plex media players."""
        plex_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            PLEX_DOMAIN, self._entry.unique_id
        )
        if plex_entry is None:
            _LOGGER.warning(
                "Cannot monitor Plex media players: linked Plex entry is missing"
            )
            return
        self._plex_entry_id = plex_entry.entry_id

        self._entry.async_on_unload(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED, self._async_state_changed
            )
        )
        self._entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._async_check_positions,
                POSITION_CHECK_INTERVAL,
            )
        )
        self.hass.async_create_task(self._async_seed_active_players())

    async def _async_seed_active_players(self) -> None:
        """Establish a baseline for Plex players already active at startup."""
        registry = entity_registry.async_get(self.hass)
        for entity in entity_registry.async_entries_for_config_entry(
            registry, self._plex_entry_id
        ):
            if entity.domain == "media_player":
                await self._async_update_player(
                    entity.entity_id, self.hass.states.get(entity.entity_id)
                )

    async def _async_state_changed(self, event: Event) -> None:
        """Handle playback updates pushed by the official Plex integration."""
        entity_id = event.data["entity_id"]
        if not entity_id.startswith("media_player."):
            return

        registry_entry = entity_registry.async_get(self.hass).async_get(entity_id)
        if (
            registry_entry is None
            or registry_entry.config_entry_id != self._plex_entry_id
        ):
            return

        await self._async_update_player(entity_id, event.data["new_state"])

    async def _async_update_player(
        self, entity_id: str, state: State | None
    ) -> None:
        """Record the playback position of one Plex media player."""
        if state is None or state.state not in {"playing", "paused"}:
            self._playbacks.pop(entity_id, None)
            return

        attributes = state.attributes
        rating_key = attributes.get("media_content_id")
        position = attributes.get("media_position")
        if rating_key is None or not isinstance(position, (int, float)):
            return

        updated_at = attributes.get("media_position_updated_at")
        if not isinstance(updated_at, datetime):
            updated_at = dt_util.utcnow()
        playback = Playback(
            rating_key=rating_key,
            playing=state.state == "playing",
            position=float(position),
            updated_at=updated_at,
            user=attributes.get("username"),
            player_name=attributes.get("friendly_name") or attributes.get("app_name"),
        )

        previous = self._playbacks.get(entity_id)
        if (
            previous is not None
            and previous.rating_key == rating_key
            and (previous.playing or playback.playing)
        ):
            playback.checked_position = previous.checked_position
        else:
            playback.checked_position = playback.position_at(dt_util.utcnow())
        self._playbacks[entity_id] = playback

        await self._async_load_marker(rating_key)
        self._async_check_positions(dt_util.utcnow())

    async def _async_load_marker(self, rating_key: int) -> None:
        """Fetch and cache a movie's final marker once per rating key."""
        if rating_key in self._markers:
            self._markers.move_to_end(rating_key)
            return

        try:
            connection = resolve_plex_connection(self.hass, self._entry.entry_id)
            marker = await self.hass.async_add_executor_job(
                get_final_credits_marker,
                connection,
                rating_key,
            )
        except Exception as err:
            _LOGGER.debug(
                "Could not read final credits marker for %s (%s)",
                rating_key,
                type(err).__name__,
            )
            return

        self._markers[rating_key] = marker
        if len(self._markers) > MARKER_CACHE_SIZE:
            self._markers.popitem(last=False)

    @callback
    def _async_check_positions(self, now: datetime) -> None:
        """Fire when playback crosses the final marker start."""
        for entity_id, playback in tuple(self._playbacks.items()):
            position = playback.position_at(now)
            marker = self._markers.get(playback.rating_key)
            if (
                marker is not None
                and playback.checked_position
                < marker["marker_start"] / 1000
                <= position
            ):
                self.hass.bus.async_fire(
                    EVENT_FINAL_CREDITS_STARTED,
                    {
                        "server": self._entry.entry_id,
                        "rating_key": playback.rating_key,
                        "title": marker["title"],
                        "view_offset": round(position * 1000),
                        "marker_start": marker["marker_start"],
                        "marker_end": marker["marker_end"],
                        "user": playback.user,
                        # Deprecated: use "player_name". Remove in 0.9.0.
                        "player": playback.player_name,
                        "player_name": playback.player_name,
                        "player_id": entity_id,
                    },
                )
            playback.checked_position = position
