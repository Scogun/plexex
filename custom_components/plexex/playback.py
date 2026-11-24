"""Monitor Plex integration media-player updates for final credits."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers import entity_registry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .common import resolve_plex_connection
from .const import EVENT_FINAL_CREDITS_STARTED, PLEX_DOMAIN
from .plex_client import get_final_credits_marker

_LOGGER = logging.getLogger(__name__)
MARKER_CACHE_SIZE = 256
POSITION_CHECK_INTERVAL = timedelta(seconds=1)


@dataclass(frozen=True)
class PlaybackAnchor:
    """Latest playback position reported by the official Plex integration."""

    rating_key: int
    state: str
    position: float
    updated_at: datetime
    title: str
    user: str | None
    player: str | None


class PlexPlaybackMonitor:
    """Use Plex media-player state updates, without polling Plex sessions."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the monitor for one linked Plex server."""
        self.hass = hass
        self.entry_id = entry.entry_id
        plex_entry = hass.config_entries.async_entry_for_domain_unique_id(
            PLEX_DOMAIN, entry.unique_id
        )
        self._plex_entry_id = plex_entry.entry_id if plex_entry else None
        self._anchors: dict[str, PlaybackAnchor] = {}
        self._last_positions: dict[str, float] = {}
        self._marker_cache: OrderedDict[int, dict | None] = OrderedDict()
        self._unsub_state_changed = None
        self._unsub_position_check = None

    def start(self) -> None:
        """Listen for state updates pushed by Plex media players."""
        if self._plex_entry_id is None:
            _LOGGER.warning(
                "Cannot monitor Plex media players: linked Plex entry is missing"
            )
            return

        self._unsub_state_changed = self.hass.bus.async_listen(
            "state_changed", self._async_state_changed
        )
        self._unsub_position_check = async_track_time_interval(
            self.hass,
            self._async_check_positions,
            POSITION_CHECK_INTERVAL,
        )
        self.hass.async_create_task(self._async_seed_active_players())

    def stop(self) -> None:
        """Stop listening for playback updates."""
        if self._unsub_state_changed is not None:
            self._unsub_state_changed()
            self._unsub_state_changed = None
        if self._unsub_position_check is not None:
            self._unsub_position_check()
            self._unsub_position_check = None

    async def _async_seed_active_players(self) -> None:
        """Establish a baseline for Plex players already active at startup."""
        assert self._plex_entry_id is not None
        registry = entity_registry.async_get(self.hass)
        for entity in entity_registry.async_entries_for_config_entry(
            registry, self._plex_entry_id
        ):
            if entity.platform != PLEX_DOMAIN or not entity.entity_id.startswith(
                "media_player."
            ):
                continue
            if state := self.hass.states.get(entity.entity_id):
                await self._async_update_player(entity.entity_id, state, baseline=True)

    async def _async_state_changed(self, event: Event) -> None:
        """Handle playback updates pushed by the official Plex integration."""
        entity_id = event.data.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id.startswith(
            "media_player."
        ):
            return

        registry_entry = entity_registry.async_get(self.hass).async_get(entity_id)
        if (
            registry_entry is None
            or registry_entry.platform != PLEX_DOMAIN
            or registry_entry.config_entry_id != self._plex_entry_id
        ):
            return

        new_state = event.data.get("new_state")
        if new_state is None:
            self._anchors.pop(entity_id, None)
            self._last_positions.pop(entity_id, None)
            return

        await self._async_update_player(entity_id, new_state)

    async def _async_update_player(
        self, entity_id: str, state: State, *, baseline: bool = False
    ) -> None:
        """Update a playback anchor from one Plex media-player state."""
        if state.state not in {"playing", "paused"}:
            self._anchors.pop(entity_id, None)
            self._last_positions.pop(entity_id, None)
            return

        attributes = state.attributes
        rating_key = attributes.get("media_content_id")
        position = attributes.get("media_position")
        if rating_key is None or not isinstance(position, (int, float)):
            return

        updated_at_value = attributes.get("media_position_updated_at")
        if isinstance(updated_at_value, datetime):
            updated_at = updated_at_value
        else:
            updated_at = dt_util.parse_datetime(updated_at_value) or dt_util.utcnow()
        anchor = PlaybackAnchor(
            rating_key=rating_key,
            state=state.state,
            position=float(position),
            updated_at=dt_util.as_utc(updated_at),
            title=str(attributes.get("media_title") or "Unknown Plex media"),
            user=_optional_str(attributes.get("username")),
            player=_optional_str(
                attributes.get("friendly_name") or attributes.get("app_name")
            ),
        )

        previous_anchor = self._anchors.get(entity_id)
        self._anchors[entity_id] = anchor
        marker = await self._async_get_marker(rating_key)
        now = dt_util.utcnow()
        current_position = _estimated_position(anchor, now)

        if (
            not baseline
            and previous_anchor is not None
            and previous_anchor.rating_key == rating_key
        ):
            previous_position = self._last_positions.get(entity_id)
            if previous_position is None:
                previous_position = _estimated_position(previous_anchor, now)
            self._maybe_fire(
                replace(previous_anchor, position=previous_position),
                replace(anchor, position=current_position),
                marker,
            )
        self._last_positions[entity_id] = current_position

    async def _async_get_marker(self, rating_key: int) -> dict | None:
        """Fetch and cache a movie's final marker once per rating key."""
        if rating_key in self._marker_cache:
            self._marker_cache.move_to_end(rating_key)
            return self._marker_cache[rating_key]

        try:
            connection = resolve_plex_connection(self.hass, self.entry_id)
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
            return None

        self._marker_cache[rating_key] = marker
        self._marker_cache.move_to_end(rating_key)
        if len(self._marker_cache) > MARKER_CACHE_SIZE:
            self._marker_cache.popitem(last=False)
        return marker

    async def _async_check_positions(self, _now: datetime) -> None:
        """Check playback locally between state updates from Plex."""
        now = dt_util.utcnow()
        for entity_id, anchor in tuple(self._anchors.items()):
            current_position = _estimated_position(anchor, now)
            previous_position = self._last_positions.get(entity_id)
            if previous_position is not None:
                marker = self._marker_cache.get(anchor.rating_key)
                self._maybe_fire(
                    replace(anchor, position=previous_position),
                    replace(anchor, position=current_position),
                    marker,
                )
            self._last_positions[entity_id] = current_position

    def _maybe_fire(
        self,
        previous_anchor: PlaybackAnchor,
        anchor: PlaybackAnchor,
        marker: dict | None
    ) -> None:
        """Fire when reported playback crosses the final marker start."""
        was_playing = previous_anchor.state == "playing"
        is_playing = anchor.state == "playing"
        if (
            marker is None
            or not (is_playing or was_playing and anchor.state == "paused")
            or not (
                previous_anchor.position
                < marker["marker_start"] / 1000
                <= anchor.position
            )
        ):
            return

        self.hass.bus.async_fire(
            EVENT_FINAL_CREDITS_STARTED,
            {
                "server": self.entry_id,
                "rating_key": anchor.rating_key,
                "title": marker["title"],
                "view_offset": round(anchor.position * 1000),
                "marker_start": marker["marker_start"],
                "marker_end": marker["marker_end"],
                "user": anchor.user,
                "player": anchor.player,
            },
        )


def _estimated_position(anchor: PlaybackAnchor, now: datetime) -> float:
    """Estimate playback position from the latest Plex position update."""
    if anchor.state != "playing":
        return anchor.position
    elapsed = max(0.0, (now - anchor.updated_at).total_seconds())
    return anchor.position + elapsed


def _optional_str(value: object) -> str | None:
    """Normalize an optional state attribute to a string."""
    return str(value) if value is not None else None
