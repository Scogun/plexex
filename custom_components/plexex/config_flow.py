"""Config flow for PlexEx."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import CONF_PLEX_ENTRY_ID, DOMAIN

class PlexExConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure PlexEx by selecting an existing official Plex entry."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Select the Plex server to extend."""
        all_plex_entries = self.hass.config_entries.async_entries("plex")
        if not all_plex_entries:
            return self.async_abort(reason="no_plex_servers")

        configured_plex_entry_ids = {
            entry.data.get(CONF_PLEX_ENTRY_ID)
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        }
        plex_entries = [
            entry for entry in all_plex_entries
            if entry.entry_id not in configured_plex_entry_ids
        ]
        if not plex_entries:
            return self.async_abort(reason="already_configured")

        options = [
            {"value": entry.entry_id, "label": entry.data.get("server") or entry.title}
            for entry in plex_entries
        ]

        if user_input is not None:
            plex_entry_id = user_input[CONF_PLEX_ENTRY_ID]
            plex_entry = self.hass.config_entries.async_get_entry(plex_entry_id)
            if plex_entry is None or plex_entry.domain != "plex":
                return self.async_abort(reason="no_plex_servers")

            await self.async_set_unique_id(plex_entry_id)
            self._abort_if_unique_id_configured()
            server_name = plex_entry.data.get("server") or plex_entry.title
            return self.async_create_entry(
                title=f"PlexEx ({server_name})",
                data={CONF_PLEX_ENTRY_ID: plex_entry_id},
            )

        schema = vol.Schema({
            vol.Required(CONF_PLEX_ENTRY_ID): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        })
        return self.async_show_form(step_id="user", data_schema=schema)
