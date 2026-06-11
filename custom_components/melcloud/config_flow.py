"""Config flow for the MELCloud integration."""

from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


class MelCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a MELCloud config flow.

    This custom integration intentionally keeps the same domain as Home
    Assistant core so an existing MELCloud config entry is reused.
    """

    VERSION = 1

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Abort manual setup because an existing core config entry is required."""
        return self.async_abort(reason="existing_core_entry_required")

    async def async_step_reauth(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Abort reauthentication to avoid collecting credentials in this fork."""
        return self.async_abort(reason="existing_core_entry_required")
