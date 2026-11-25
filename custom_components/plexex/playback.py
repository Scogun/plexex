"""Monitor Plex integration media-player updates for playback markers."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Collection
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
from .const import EVENT_PREFIX, MARKER_ENDED, MARKER_STARTED, PLEX_DOMAIN
from .models import Marker, MediaMarkers
from .plex_client import get_markers

_LOGGER = logging.getLogger(__name__)
MARKER_CACHE_SIZE = 256
POSITION_CHECK_INTERVAL = timedelta(seconds=1)
# Checked position of a playback that just began: before any marker, so a
# marker at the very beginning of the media is still entered.
BEFORE_MEDIA_START = -1.0


@dataclass
class Playback:
    """Latest playback position reported for one Plex media player."""

    rating_key: int
    playing: bool
    position: float
    updated_at: datetime
    user: str | None
    player_name: str | None
    checked_position: float = BEFORE_MEDIA_START

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
        self._markers: OrderedDict[int, MediaMarkers | None] = OrderedDict()

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
                    entity.entity_id,
                    self.hass.states.get(entity.entity_id),
                    seed=True,
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
        self, entity_id: str, state: State | None, *, seed: bool = False
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
        if previous is not None and previous.rating_key == rating_key:
            if previous.playing or playback.playing:
                playback.checked_position = previous.checked_position
            else:
                # Scrubbing while paused only moves the baseline.
                playback.checked_position = playback.position
        elif seed:
            # Already running when PlexEx started: report nothing it passed.
            playback.checked_position = playback.position_at(dt_util.utcnow())
        self._playbacks[entity_id] = playback

        await self._async_load_markers(rating_key)
        self._async_check_positions(dt_util.utcnow())

    async def _async_load_markers(self, rating_key: int) -> None:
        """Fetch and cache the markers of a media item once per rating key."""
        if rating_key in self._markers:
            self._markers.move_to_end(rating_key)
            return

        try:
            connection = resolve_plex_connection(self.hass, self._entry.entry_id)
            markers = await self.hass.async_add_executor_job(
                get_markers,
                connection,
                rating_key,
            )
        except Exception as err:
            _LOGGER.debug(
                "Could not read markers for %s (%s)",
                rating_key,
                type(err).__name__,
            )
            return

        self._markers[rating_key] = markers
        if len(self._markers) > MARKER_CACHE_SIZE:
            self._markers.popitem(last=False)

    @callback
    def async_get_current_marker(
        self, entity_id: str, kinds: Collection[str] = ()
    ) -> Marker | None:
        """Return the marker a Plex media player is inside right now.

        Only markers of the given kinds are considered; none means any kind.
        """
        playback = self._playbacks.get(entity_id)
        if playback is None:
            return None
        media = self._markers.get(playback.rating_key)
        if media is None:
            return None
        position = playback.position_at(dt_util.utcnow()) * 1000
        for marker in media.markers:
            if marker.start <= position < marker.end and (
                not kinds or marker.kind in kinds
            ):
                return marker
        return None

    @callback
    def _async_check_positions(self, now: datetime) -> None:
        for entity_id, playback in tuple(self._playbacks.items()):
            if playback.rating_key not in self._markers:
                continue
            position = playback.position_at(now)
            media = self._markers[playback.rating_key]
            for marker in media.markers if media is not None else ():
                start, end = marker.start / 1000, marker.end / 1000
                if playback.checked_position < start <= position < end:
                    self._async_fire(
                        entity_id, playback, media, marker, MARKER_STARTED, position
                    )
                elif start <= playback.checked_position < end <= position:
                    self._async_fire(
                        entity_id, playback, media, marker, MARKER_ENDED, position
                    )
            playback.checked_position = position

    @callback
    def _async_fire(
        self,
        entity_id: str,
        playback: Playback,
        media: MediaMarkers,
        marker: Marker,
        phase: str,
        position: float,
    ) -> None:
        """Fire the event of a marker that playback entered or left."""
        self.hass.bus.async_fire(
            f"{EVENT_PREFIX}{marker.kind}_{phase}",
            {
                "server": self._entry.entry_id,
                "rating_key": playback.rating_key,
                "media_type": media.media_type,
                "title": media.title,
                "show_title": media.show_title,
                "season": media.season,
                "episode": media.episode,
                "marker_type": marker.type,
                "final": marker.final,
                "view_offset": round(position * 1000),
                "marker_start": marker.start,
                "marker_end": marker.end,
                "user": playback.user,
                # Deprecated: use "player_name". Remove in 0.9.0.
                "player": playback.player_name,
                "player_name": playback.player_name,
                "player_id": entity_id,
            },
        )
