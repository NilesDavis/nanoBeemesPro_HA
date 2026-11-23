"""DataUpdateCoordinator for nanoBeemesPro Reader."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    EMETER_ENDPOINT,
    EST_MIN_DELTA_WH,
    POWER_DELTA_OBIS_SOURCES,
    POWER_ESTIMATE_KEY,
    STATUS_MISS_NEEDED,
    STATUS_OK_NEEDED,
)

_LOGGER = logging.getLogger(__name__)

# Backoff settings
_BACKOFF_INITIAL = 10       # seconds after first failure
_BACKOFF_MAX = 300          # cap at 5 minutes
_BACKOFF_MULTIPLIER = 2


class BsedLesekopfCoordinator(DataUpdateCoordinator):
    """Fetches data from the BSED nanoBeemesPro emeter.json endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        scan_interval: int,
        power_factor: float = 1.0,
        invert_power: bool = False,
    ) -> None:
        self.host = host
        self.url = f"http://{host}{EMETER_ENDPOINT}"
        self._session = aiohttp.ClientSession()
        self._scan_interval = scan_interval
        self._power_factor = power_factor
        self._invert_power = invert_power
        self._consecutive_failures = 0
        self._device_was_available = True  # tracks last known state for logging

        # --- Delta-Schätzung + Messquellen-Status -----------------------------
        self._last_energy: tuple[float, float] | None = None  # (1.8.0, 2.8.0) in kWh
        self._last_success_ts: float | None = None
        self._est_power: float | None = None          # letzter gültiger Schätzwert in W
        self._status = "off"                          # 'on' = echte 16.7.0 vertrauenswürdig
        self._streak_ok = 0
        self._streak_miss = 0
        # ----------------------------------------------------------------------

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch and parse emeter.json. Returns dict: descr -> raw_value (as string)."""
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

        # Parse array of {descr, value} into a flat dict - RAW VALUES ONLY
        parsed: dict[str, str] = {}
        for entry in raw["eminfo"]:
            descr = entry.get("descr", "")
            value = entry.get("value", "")
            parsed[descr] = value

        parsed["__emstatus"] = str(raw.get("emstatus", ""))
        parsed["__pinstatus"] = str(raw.get("pinstatus", ""))

        # 1) Messquellen-Status (Hysterese gegen Flattern): Ist der ECHTE 16.7.0 da?
        _update_measurement_status(self, parsed)
        parsed["__measurement_source"] = self._status

        # 2) Delta-Schätzung der Wirkleistung aus den Energie-Zählerständen
        self._update_estimation(parsed)
        parsed[POWER_ESTIMATE_KEY] = (
            "0.0" if self._est_power is None else f"{self._est_power:.1f}"
        )

        _LOGGER.debug("Fetched emeter data: %s", parsed)
        return parsed

    def _update_estimation(self, parsed: dict[str, str]) -> None:
        """Delta-basierte Schätzung der aktuellen Wirkleistung in W.

        Korrekte Einheiten-Formel (gegen reales Keller-Profil validiert):
            Leistung[W] = dE[Wh] * 3600 / dt[s]

        Eine Aktualisierung gibt es nur, wenn sich ein Energie-Zählerstand um
        >= EST_MIN_DELTA_WH ändert (sonst bleibt der letzte Wert stehen). Grund:
        die Zählerstände haben 3 Nachkommastellen (~1 Wh Auflösung); darunter
        wäre das Delta Rauschen.
        """
        try:
            bezug = float(parsed.get(POWER_DELTA_OBIS_SOURCES[0]) or 0.0)
            einsp = float(parsed.get(POWER_DELTA_OBIS_SOURCES[1]) or 0.0)
        except (ValueError, TypeError):
            return
        now = time.time()

        if self._last_energy is None or self._last_success_ts is None:
            # Erster Poll: noch kein Delta möglich — nur Referenz setzen.
            self._last_energy = (bezug, einsp)
            self._last_success_ts = now
            return

        dt = now - self._last_success_ts
        d_bezug = (bezug - self._last_energy[0]) * 1000.0  # Wh
        d_einsp = (einsp - self._last_energy[1]) * 1000.0  # Wh

        self._last_energy = (bezug, einsp)
        self._last_success_ts = now

        if dt <= 0:
            return
        # Auflösungs-/Rausch-Grenze
        if abs(d_bezug) < EST_MIN_DELTA_WH and abs(d_einsp) < EST_MIN_DELTA_WH:
            return

        # Richtung: betragsmäßig größerer Zählerstand gewinnt;
        # Einspeisung negativ, Bezug positiv.
        if abs(d_bezug) >= abs(d_einsp):
            self._est_power = d_bezug * 3600.0 / dt   # W
        else:
            self._est_power = -d_einsp * 3600.0 / dt  # W (negativ = Einspeisung)

    @property
    def measurement_source(self) -> str:
        """'on' wenn echte 16.7.0-Werte vertrauenswürdig ankommen, sonst 'off'."""
        return self._status

    @property
    def power_estimate(self) -> float | None:
        """Letzte Delta-Schätzung in W (None = noch kein brauchbares Delta)."""
        return self._est_power

    @property
    def power_effective(self) -> float | None:
        """'Always-usable' Wirkleistung (mit Vorzeichen) in W.

        Echter 16.7.0 (mit power_factor/invert skaliert) wenn Messquelle 'on',
        sonst die Delta-Schätzung. Gleiche Semantik wie der gleichnamige Sensor —
        hier zentral, damit mehrere Sensoren dieselbe Quelle nutzen.
        """
        if self.data is None:
            return None
        if self._status == "on":
            real16 = self.data.get("16.7.0")
            if real16 not in (None, ""):
                try:
                    value = float(real16)
                except (ValueError, TypeError):
                    pass
                else:
                    value *= self._power_factor
                    if self._invert_power:
                        value *= -1
                    return value
        # sonst Delta-Schätzung (bereits echte W, kein power_factor anwenden)
        return self._est_power

    @property
    def power_import(self) -> float | None:
        """Entnahme (Bezug) in W, immer >= 0. Aus dem effektiven Vorzeichen-Wert."""
        eff = self.power_effective
        if eff is None:
            return None
        return max(0.0, eff)

    @property
    def power_export(self) -> float | None:
        """Einspeisung in W, immer >= 0. Aus dem effektiven Vorzeichen-Wert."""
        eff = self.power_effective
        if eff is None:
            return None
        return max(0.0, -eff)

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


def _update_measurement_status(coordinator: BsedLesekopfCoordinator, parsed: dict[str, str]) -> None:
    """Hysterese-Aktualisierung des Messquellen-Status.

    'on'  erst nach STATUS_OK_NEEDED (3) gültigen 16.7.0-Werten in Folge.
    'off' erst nach STATUS_MISS_NEEDED (5) fehlenden Werten in Folge (nur wenn 'on').
    Kurze Aussetzer kippen den Zustand nicht.
    """
    real16_raw = parsed.get("16.7.0")
    valid = False
    if real16_raw is not None and real16_raw != "":
        try:
            float(real16_raw)
            valid = True
        except (ValueError, TypeError):
            valid = False

    if valid:
        coordinator._streak_ok += 1
        coordinator._streak_miss = 0
        if coordinator._streak_ok >= STATUS_OK_NEEDED:
            coordinator._status = "on"
    else:
        coordinator._streak_miss += 1
        coordinator._streak_ok = 0
        if coordinator._status == "on" and coordinator._streak_miss >= STATUS_MISS_NEEDED:
            coordinator._status = "off"