"""nanoBeemesPro Reader integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, OBIS_SENSORS
from .coordinator import BsedLesekopfCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_POWER_FACTOR = "power_factor"
CONF_INVERT_POWER = "invert_power"

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up nanoBeemesPro Reader from a config entry."""
    host = entry.data[CONF_HOST]
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    power_factor = entry.data.get(CONF_POWER_FACTOR, 1.0)
    invert_power = entry.data.get(CONF_INVERT_POWER, False)

    # Cleanup old entities from previous versions
    await _async_migrate_old_entities(hass, entry)

    coordinator = BsedLesekopfCoordinator(
        hass, host, scan_interval, power_factor, invert_power
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload integration when options are changed
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_migrate_old_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove old entity IDs that are no longer needed."""
    entity_registry = async_get_entity_registry(hass)
    host = entry.data[CONF_HOST]
    
    # List of old OBIS codes to remove (versions < 1.2.0)
    # These are the entity IDs created BEFORE we had _raw sensors
    old_entity_ids_to_remove = []
    
    # Build list of old entity_ids that should be removed
    for obis_key in OBIS_SENSORS.keys():
        obis_id = obis_key.replace(".", "_")
        # Old unique_id format (without _raw, without scaling distinction)
        old_unique_id = f"{host}_{obis_id}"
        
        # Try to find and remove the old entity
        for entity in entity_registry.entities.values():
            if entity.unique_id == old_unique_id and entity.domain == "sensor":
                old_entity_ids_to_remove.append(entity.entity_id)
    
    # Remove old entities
    if old_entity_ids_to_remove:
        _LOGGER.info(
            "Removing old entities from previous integration version: %s",
            old_entity_ids_to_remove,
        )
        for entity_id in old_entity_ids_to_remove:
            entity_registry.async_remove(entity_id)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when settings change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: BsedLesekopfCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_close()
    return unloaded
