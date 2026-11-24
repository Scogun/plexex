"""Config flow for PlexEx."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.selector import SelectOptionDict
from .const import CONF_PLEX_ENTRY_ID, DOMAIN, PLEX_DOMAIN

class PlexExConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure PlexEx by selecting an existing official Plex entry."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Select the Plex server to extend."""
        all_plex_entries = self.hass.config_entries.async_entries(
            PLEX_DOMAIN, include_ignore=False
        )
        if not all_plex_entries:
            return self.async_abort(reason="no_plex_servers")

        configured_server_ids = {
            entry.unique_id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        }
        plex_entries = {
            server_id: entry
            for entry in all_plex_entries
            if (server_id := entry.unique_id)
            and server_id not in configured_server_ids
        }
        if not plex_entries:
            return self.async_abort(reason="already_configured")

        options = [
            SelectOptionDict(
                value=server_id,
                label=str(entry.data.get("server") or entry.title),
            )
            for server_id, entry in plex_entries.items()
        ]

        if user_input is not None:
            server_id = user_input[CONF_PLEX_ENTRY_ID]
            plex_entry = plex_entries.get(server_id)
            if plex_entry is None:
                return self.async_abort(reason="no_plex_servers")

            await self.async_set_unique_id(server_id)
            self._abort_if_unique_id_configured()
            server_name = plex_entry.data.get("server") or plex_entry.title
            return self.async_create_entry(
                title=f"PlexEx ({server_name})",
                data={},
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
