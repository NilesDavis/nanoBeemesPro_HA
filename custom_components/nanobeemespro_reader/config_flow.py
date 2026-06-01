"""Config flow for nanoBeemesPro Reader integration."""
from __future__ import annotations

import asyncio
import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, EMETER_ENDPOINT


async def _test_connection(hass: HomeAssistant, host: str) -> str | None:
    """Try to connect and return None on success, error key on failure."""
    url = f"http://{host}{EMETER_ENDPOINT}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    return "cannot_connect"
                data = await resp.json(content_type=None)
                if "eminfo" not in data:
                    return "invalid_response"
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return "cannot_connect"
    except Exception:
        return "invalid_response"
    return None


class BsedLesekopfConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for nanoBeemesPro Reader."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip().rstrip("/")
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

            # Prevent duplicate entries for the same host
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            error = await _test_connection(self.hass, host)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=f"nanoBeemesPro Reader ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_SCAN_INTERVAL: scan_interval,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default="10.0.3.90"): str,
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                        int, vol.Range(min=2, max=60)
                    ),
                }
            ),
            errors=errors,
        )
