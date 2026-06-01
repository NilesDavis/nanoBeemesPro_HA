"""DataUpdateCoordinator for nanoBeemesPro Reader."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, EMETER_ENDPOINT

_LOGGER = logging.getLogger(__name__)


class BsedLesekopfCoordinator(DataUpdateCoordinator):
    """Fetches data from the BSED nanoBeemesPro emeter.json endpoint."""

    def __init__(self, hass: HomeAssistant, host: str, scan_interval: int) -> None:
        self.host = host
        self.url = f"http://{host}{EMETER_ENDPOINT}"
        self._session = aiohttp.ClientSession()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch and parse emeter.json. Returns dict: descr -> value."""
        try:
            async with self._session.get(
                self.url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP {resp.status} from {self.url}")
                raw = await resp.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout connecting to {self.url}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

        if "eminfo" not in raw:
            raise UpdateFailed("Unexpected response: 'eminfo' key missing")

        # Parse array of {descr, value} into a flat dict
        parsed: dict[str, str] = {}
        for entry in raw["eminfo"]:
            descr = entry.get("descr", "")
            value = entry.get("value", "")
            # Strip HTML entities like &auml; from descr (not needed for our keys,
            # but keep raw value as-is for string sensors)
            parsed[descr] = value

        # Also store status flags
        parsed["__emstatus"] = str(raw.get("emstatus", ""))
        parsed["__pinstatus"] = str(raw.get("pinstatus", ""))

        _LOGGER.debug("Fetched emeter data: %s", parsed)
        return parsed

    async def async_close(self) -> None:
        """Close the aiohttp session."""
        await self._session.close()
