"""Sensor platform for nanoBeemesPro Reader."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OBIS_SENSORS, ENERGY_OBIS_CODES
from .coordinator import BsedLesekopfCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_POWER_FACTOR = "power_factor"
CONF_INVERT_POWER = "invert_power"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: BsedLesekopfCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Create sensors for each OBIS code
    for obis_key, meta in OBIS_SENSORS.items():
        # For ALL values (energy + power): create BOTH raw and scaled sensors
        # Raw sensor (no scaling)
        entities.append(
            BsedSensor(coordinator, entry, obis_key, meta, is_raw=True)
        )
        # Scaled sensor (with power_factor)
        entities.append(
            BsedSensor(coordinator, entry, obis_key, meta, is_raw=False)
        )

    # --- Zusatz-Sensoren (v1.3) ---
    # Delta-Schätzung (immer verfügbar, auch wenn der Zähler 16.7.0 nicht liefert)
    entities.append(BsedPowerEstimateSensor(coordinator, entry))
    # Messquellen-Status: 'on' (echter 16.7.0) / 'off' (Schätzung)
    entities.append(BsedMeasurementSourceSensor(coordinator, entry))
    # "Always-usable": echter Wert wenn 'on', sonst Schätzung (Anzeige)
    entities.append(BsedPowerEffectiveSensor(coordinator, entry))

    # Always add Zählernummer as a diagnostic sensor
    entities.append(BsedZaehlerSensor(coordinator, entry))

    async_add_entities(entities)


class BsedSensor(CoordinatorEntity, SensorEntity):
    """A numeric sensor reading from emeter.json."""

    def __init__(
        self,
        coordinator: BsedLesekopfCoordinator,
        entry: ConfigEntry,
        obis_key: str,
        meta: dict,
        is_raw: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self._obis_key = obis_key
        self._meta = meta
        self._entry = entry
        self._is_raw = is_raw
        host = entry.data[CONF_HOST]

        # Entity ID based on OBIS code
        obis_id = obis_key.replace(".", "_")
        if is_raw:
            self._attr_unique_id = f"{host}_{obis_id}_raw"
        else:
            self._attr_unique_id = f"{host}_{obis_id}"

        # Friendly name: show if it's raw or scaled
        if is_raw:
            self._attr_name = f"{obis_key} - {meta['name']} (Rohdaten)"
        else:
            self._attr_name = f"{obis_key} - {meta['name']}"

        self._attr_native_unit_of_measurement = meta["unit"]
        self._attr_icon = meta["icon"]

        dc = meta.get("device_class")
        self._attr_device_class = SensorDeviceClass(dc) if dc else None

        sc = meta.get("state_class")
        self._attr_state_class = SensorStateClass(sc) if sc else None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=f"nanoBeemesPro Reader ({host})",
            manufacturer="BSED GmbH",
            model="nanoBeemesPro",
            configuration_url=f"http://{host}",
        )

    @property
    def native_value(self):
        """Return the current sensor value."""
        if self.coordinator.data is None:
            return None

        raw = self.coordinator.data.get(self._obis_key)
        if raw is None:
            return None

        try:
            value = float(raw)
        except (ValueError, TypeError):
            _LOGGER.warning("Cannot convert '%s' to float for %s", raw, self._obis_key)
            return None

        # Apply transformations only to non-raw sensors
        if not self._is_raw:
            # Apply power_factor to ALL measured values (energy + power)
            power_factor = self._entry.data.get("power_factor", 1.0)
            value *= power_factor

            # Apply invert_power to 16.7.0 (current power) AFTER scaling
            if self._obis_key == "16.7.0":
                invert_power = self._entry.data.get("invert_power", False)
                if invert_power:
                    value *= -1

        return value

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None


class _BaseExtraSensor(CoordinatorEntity, SensorEntity):
    """Gemeinsames Basis-/Device-Info für die Zusatz-Sensoren (keine OBIS-Bindung)."""

    def __init__(self, coordinator: BsedLesekopfCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._host = entry.data[CONF_HOST]
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"nanoBeemesPro Reader ({self._host})",
            manufacturer="BSED GmbH",
            model="nanoBeemesPro",
            configuration_url=f"http://{self._host}",
        )


class BsedPowerEstimateSensor(_BaseExtraSensor):
    """Geschätzte Wirkleistung, aus Energie-Zählerstands-Deltas (immer verfügbar).

    Kein power_factor/invert anwenden: Der Zählerstand ist bereits skaliert
    (×50-Faktor steckt schon im Zählerstand), ein erneutes Multiplizieren wäre falsch.
    """

    def __init__(self, coordinator: BsedLesekopfCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._host}_power_estimate"
        self._attr_name = "Geschätzte Wirkleistung"
        self._attr_icon = "mdi:chart-line"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        return self.coordinator.power_estimate

    @property
    def extra_state_attributes(self) -> dict | None:
        return {"estimate_source": "energy_delta", "basis": "1.8.0/2.8.0-Zählerstände"}

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None


class BsedMeasurementSourceSensor(_BaseExtraSensor):
    """Zeigt, ob der echte 16.7.0-Wert gerade als Quelle dient ('on' = echte Messung)
    oder auf die Schätzung zurückgegriffen wird ('off'). Hysterese gegen Flattern."""

    def __init__(self, coordinator: BsedLesekopfCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._host}_measurement_source"
        self._attr_name = "Messquelle (Echt/Schätzung)"
        self._attr_icon = "mdi:swap-horizontal"

    @property
    def native_value(self) -> str:
        return self.coordinator.measurement_source  # 'on' | 'off'

    @property
    def extra_state_attributes(self) -> dict | None:
        data = self.coordinator.data
        return {
            "emstatus": data.get("__emstatus") if data else None,
            "pinstatus": data.get("__pinstatus") if data else None,
            "ok_needed": 3,
            "miss_needed": 5,
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None


class BsedPowerEffectiveSensor(_BaseExtraSensor):
    """'Always-usable' Wirkleistung: echter 16.7.0 wenn verfügbar (Status 'on'),
    sonst der Delta-Schätzwert. Für Dashboard/Anzeige gedacht.

    Achtung bei Steuerung/Automation: Die Schätzung ist ein Energie-Mittel über das
    Poll-Intervall (geglättet), nicht die instantane Leistung. Für Schwellwert-/
    Regel-Logik besser nur eine Quelle verwenden (z.B. den echten 16.7.0 oder die
    Schätzung) plus Hysterese — nicht diesen gemischten Wert als Regler-Eingang.
    """

    def __init__(self, coordinator: BsedLesekopfCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._host}_power_effective"
        self._attr_name = "Wirkleistung (effektiv)"
        self._attr_icon = "mdi:lightning-bolt-outline"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        # echte 16.7.0 (mit gleicher Skalierung wie der echte Sensor) wenn Status 'on'
        if self.coordinator.measurement_source == "on":
            raw = self.coordinator.data.get("16.7.0")
            if raw not in (None, ""):
                try:
                    value = float(raw)
                    pf = self._entry.data.get("power_factor", 1.0)
                    value *= pf
                    if self._entry.data.get("invert_power", False):
                        value *= -1
                    return value
                except (ValueError, TypeError):
                    pass
        # sonst Delta-Schätzung (bereits echte W, kein power_factor anwenden)
        return self.coordinator.power_estimate

    @property
    def extra_state_attributes(self) -> dict | None:
        return {"used_source": self.coordinator.measurement_source}

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None


class BsedZaehlerSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor: Zählernummer."""

    def __init__(self, coordinator: BsedLesekopfCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        host = entry.data[CONF_HOST]
        self._attr_unique_id = f"{host}_zaehler_nr"
        self._attr_name = "Zählernummer"
        self._attr_icon = "mdi:counter"
        self._attr_entity_registry_enabled_default = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=f"nanoBeemesPro Reader ({host})",
            manufacturer="BSED GmbH",
            model="nanoBeemesPro",
            configuration_url=f"http://{host}",
        )

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        # The descr for Zählernummer contains HTML entity &auml; → match by value pattern
        for descr, value in self.coordinator.data.items():
            if "Nr" in descr or "nr" in descr:
                return value
        return None

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None