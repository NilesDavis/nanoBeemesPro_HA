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


def _host_schema(default_host: str = "", default_interval: int = DEFAULT_SCAN_INTERVAL):
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=default_host): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=default_interval): vol.All(
                int, vol.Range(min=2, max=60)
            ),
        }
    )


class NanoBeemesPROConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for nanoBeemesPro Reader."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip().rstrip("/")
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

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
            data_schema=_host_schema(),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return NanoBeemesPROOptionsFlow(config_entry)


class NanoBeemesPROOptionsFlow(config_entries.OptionsFlow):
    """Handle options (re-configure) for nanoBeemesPro Reader."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}

        current_host = self._config_entry.data[CONF_HOST]
        current_interval = self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        if user_input is not None:
            host = user_input[CONF_HOST].strip().rstrip("/")
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

            error = await _test_connection(self.hass, host)
            if error:
                errors["base"] = error
            else:
                # Update both data and title
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    title=f"nanoBeemesPro Reader ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_SCAN_INTERVAL: scan_interval,
                    },
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_host_schema(current_host, current_interval),
            errors=errors,
        )
