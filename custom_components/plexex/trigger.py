"""PlexEx automation triggers."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID, CONF_OFFSET, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from .const import MARKER_ENDED, MARKER_KINDS, MARKER_STARTED
from .playback import MarkerListener, async_listen_marker

_MAX_OFFSET = timedelta(minutes=5)


def _validate_offset(value: Any) -> timedelta:
    """Validate that the marker offset is within five minutes."""
    offset = cv.time_period(value)
    if abs(offset) > _MAX_OFFSET:
        raise vol.Invalid("Offset must be between -5 minutes and 5 minutes")
    return offset


_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default={}): {
            # Negative is before the marker boundary, positive after it.
            vol.Required(CONF_OFFSET, default=timedelta(0)): _validate_offset,
        },
        # Without a target the trigger follows every Plex player.
        vol.Optional(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class MarkerTrigger(Trigger):
    """Trigger when playback moves into or out of one kind of Plex marker."""

    _kind: str
    _phase: str

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return _TRIGGER_SCHEMA(config)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)
        self._offset: timedelta = (config.options or {}).get(
            CONF_OFFSET, timedelta(0)
        )
        selection = TargetSelection(config.target) if config.target else None
        self._selection = (
            selection if selection is not None and selection.has_any_target else None
        )

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""
        event = f"{self._kind}_{self._phase}"

        @callback
        def notify(data: dict[str, Any]) -> None:
            """Run the action if the marker belongs to a targeted player."""
            player_id = data["player_id"]
            if self._selection is not None:
                # Resolved on every event, so that players added to a targeted
                # device, area or label later are followed too.
                selected = async_extract_referenced_entity_ids(
                    self._hass, self._selection, expand_group=False
                )
                if player_id not in selected.referenced | selected.indirectly_referenced:
                    return
            run_action(
                {
                    **{key: value for key, value in data.items() if key != "player"},
                    ATTR_ENTITY_ID: player_id,
                    "event": event,
                    "offset": self._offset,
                },
                f"{event.replace('_', ' ')} on {data['player_name'] or player_id}",
            )

        return async_listen_marker(
            self._hass,
            MarkerListener(
                self._kind, self._phase, self._offset.total_seconds(), notify
            ),
        )


def _marker_trigger(kind: str, phase: str) -> type[MarkerTrigger]:
    """Create the trigger of one kind of marker event."""
    return type(
        f"{kind.title().replace('_', '')}{phase.title()}Trigger",
        (MarkerTrigger,),
        {"_kind": kind, "_phase": phase},
    )


TRIGGERS: dict[str, type[Trigger]] = {
    f"{kind}_{phase}": _marker_trigger(kind, phase)
    for kind in MARKER_KINDS
    for phase in (MARKER_STARTED, MARKER_ENDED)
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers PlexEx provides."""
    return TRIGGERS
