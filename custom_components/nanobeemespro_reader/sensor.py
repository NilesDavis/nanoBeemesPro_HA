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

from .const import DOMAIN, OBIS_SENSORS
from .coordinator import BsedLesekopfCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: BsedLesekopfCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for obis_key, meta in OBIS_SENSORS.items():
        entities.append(BsedSensor(coordinator, entry, obis_key, meta))

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
    ) -> None:
        super().__init__(coordinator)
        self._obis_key = obis_key
        self._meta = meta
        self._entry = entry
        host = entry.data[CONF_HOST]

        self._attr_unique_id = f"{host}_{obis_key}"
        self._attr_name = meta["name"]
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
            return float(raw)
        except (ValueError, TypeError):
            _LOGGER.warning("Cannot convert '%s' to float for %s", raw, self._obis_key)
            return None

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
