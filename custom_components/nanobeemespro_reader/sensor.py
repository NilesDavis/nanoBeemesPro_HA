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
