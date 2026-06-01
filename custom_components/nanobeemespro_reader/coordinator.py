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

# Backoff settings
_BACKOFF_INITIAL = 10       # seconds after first failure
_BACKOFF_MAX = 300          # cap at 5 minutes
_BACKOFF_MULTIPLIER = 2


class BsedLesekopfCoordinator(DataUpdateCoordinator):
    """Fetches data from the BSED nanoBeemesPro emeter.json endpoint."""

    def __init__(self, hass: HomeAssistant, host: str, scan_interval: int) -> None:
        self.host = host
        self.url = f"http://{host}{EMETER_ENDPOINT}"
        self._session = aiohttp.ClientSession()
        self._scan_interval = scan_interval
        self._consecutive_failures = 0
        self._device_was_available = True  # tracks last known state for logging

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
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            self._handle_failure(err)
            raise UpdateFailed(str(err)) from err

        if "eminfo" not in raw:
            self._handle_failure("'eminfo' key missing in response")
            raise UpdateFailed("Unexpected response: 'eminfo' key missing")

        # Successful fetch — reset failure state
        self._on_success()

        # Parse array of {descr, value} into a flat dict
        parsed: dict[str, str] = {}
        for entry in raw["eminfo"]:
            descr = entry.get("descr", "")
            value = entry.get("value", "")
            parsed[descr] = value

        parsed["__emstatus"] = str(raw.get("emstatus", ""))
        parsed["__pinstatus"] = str(raw.get("pinstatus", ""))

        _LOGGER.debug("Fetched emeter data: %s", parsed)
        return parsed

    def _handle_failure(self, reason: object) -> None:
        """Track consecutive failures, log on first occurrence, apply backoff."""
        self._consecutive_failures += 1

        if self._device_was_available:
            _LOGGER.warning(
                "nanoBeemesPro at %s is unavailable: %s. "
                "Will retry with exponential backoff.",
                self.host,
                reason,
            )
            self._device_was_available = False

        # Calculate backoff interval, capped at _BACKOFF_MAX
        backoff = min(
            _BACKOFF_INITIAL * (_BACKOFF_MULTIPLIER ** (self._consecutive_failures - 1)),
            _BACKOFF_MAX,
        )
        new_interval = timedelta(seconds=backoff)

        if self.update_interval != new_interval:
            _LOGGER.debug(
                "Backoff: next retry in %s seconds (failure #%d)",
                backoff,
                self._consecutive_failures,
            )
            self.update_interval = new_interval

    def _on_success(self) -> None:
        """Reset failure tracking and restore normal poll interval."""
        if not self._device_was_available:
            _LOGGER.info(
                "nanoBeemesPro at %s is available again after %d failure(s).",
                self.host,
                self._consecutive_failures,
            )

        self._consecutive_failures = 0
        self._device_was_available = True

        normal_interval = timedelta(seconds=self._scan_interval)
        if self.update_interval != normal_interval:
            self.update_interval = normal_interval

    async def async_close(self) -> None:
        """Close the aiohttp session."""
        await self._session.close()
