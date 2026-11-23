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

# Suffixe der Zusatz-Sensoren (ohne Host-Präfix), die der aktuelle Code erzeugt.
# Werden für die Cleanup-Migration als "gültig" betrachtet.
_EXTRA_SENSOR_SUFFIXES = ("power_estimate", "power_effective", "measurement_source")

# v1.4: Richtungs-Sensoren (Einspeisung/Entnahme) — eigene unique_id-Formate,
# die _EXTRA_SENSOR_SUFFIXES nicht abdeckt (OBIS-Block + separater Block).
_R2L_EFFECTIVE_SUFFIXES = ("power_import_effective", "power_export_effective")
_R2L_RAW_SUFFIXES = ("16_7_0_import_raw", "16_7_0_export_raw")


def _current_unique_ids(host: str) -> set[str]:
    """Alle unique_ids, die sensor.py aktuell für einen Host erzeugt."""
    ids = set()
    for obis_key in OBIS_SENSORS:
        obis_id = obis_key.replace(".", "_")
        ids.add(f"{host}_{obis_id}")
        ids.add(f"{host}_{obis_id}_raw")
    ids.add(f"{host}_zaehler_nr")
    for suffix in _EXTRA_SENSOR_SUFFIXES:
        ids.add(f"{host}_{suffix}")
    for suffix in _R2L_EFFECTIVE_SUFFIXES + _R2L_RAW_SUFFIXES:
        ids.add(f"{host}_{suffix}")
    return ids


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up nanoBeemesPro Reader from a config entry."""
    host = entry.data[CONF_HOST]
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    power_factor = entry.data.get(CONF_POWER_FACTOR, 1.0)
    invert_power = entry.data.get(CONF_INVERT_POWER, False)

    # Cleanup old/verwaiste Entities aus vorherigen Versionen
    await _async_migrate_old_entities(hass, entry, host)

    coordinator = BsedLesekopfCoordinator(
        hass, host, scan_interval, power_factor, invert_power
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload integration when options are changed
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_migrate_old_entities(
    hass: HomeAssistant, entry: ConfigEntry, host: str
) -> None:
    """Entfernt Sensor-Entities dieses Hosts, die der aktuelle Code NICHT (mehr) erzeugt.

    Abgedeckt werden:
      - Altlasten mit OLD Punkt-Format (z.B. `10.0.3.90_1.8.0` statt `_1_8_0`),
        die aus Versionen <1.2.0 als verwaiste `unavailable`-Reste stehen blieben.
      - Entities, die von einer früheren Version erzeugt wurden und heute keine
        Entsprechung mehr in sensor.py haben.

    Bewusst NICHT gelöscht werden die aktuell erzeugten Sensoren (inkl. der
    berechneten `{host}_{obis_id}` Variante) — die frühere Migration entfernte
    fälschlich auch die eigene nicht-Roh-Entity (destruktiver Bug).
    """
    entity_registry = async_get_entity_registry(hass)
    valid = _current_unique_ids(host)

    to_remove = []
    for entity in entity_registry.entities.values():
        if entity.domain != "sensor":
            continue
        uid = entity.unique_id or ""
        # Nur Entities dieses Geräts (Host-Präfix) behandeln
        if not uid.startswith(f"{host}_"):
            continue
        if uid not in valid:
            to_remove.append((entity.entity_id, uid))

    if to_remove:
        _LOGGER.info(
            "nanoBeemesPro (%s): remove old/stale entities: %s",
            host,
            [f"{eid} ({uid})" for eid, uid in to_remove],
        )
        for entity_id, _ in to_remove:
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