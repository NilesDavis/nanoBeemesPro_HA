"""Constants for the nanoBeemesPro Reader integration."""

DOMAIN = "nanobeemespro_reader"
DEFAULT_SCAN_INTERVAL = 5  # seconds
DEFAULT_HOST = ""
DEFAULT_POWER_FACTOR = 1.0  # no multiplication by default
DEFAULT_INVERT_POWER = False  # don't invert power by default

EMETER_ENDPOINT = "/emeter.json"

# Mapping: descr-Wert aus JSON → (sensor_name, unit, device_class, state_class)
OBIS_SENSORS = {
    "1.8.0": {
        "name": "Wirkenergie Bezug gesamt",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:transmission-tower-import",
    },
    "1.8.1": {
        "name": "Wirkenergie Bezug Tarif 1",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:transmission-tower-import",
    },
    "1.8.2": {
        "name": "Wirkenergie Bezug Tarif 2",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:transmission-tower-import",
    },
    "2.8.0": {
        "name": "Wirkenergie Einspeisung gesamt",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:transmission-tower-export",
    },
    "2.8.1": {
        "name": "Wirkenergie Einspeisung Tarif 1",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:transmission-tower-export",
    },
    "2.8.2": {
        "name": "Wirkenergie Einspeisung Tarif 2",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:transmission-tower-export",
    },
    "16.7.0": {
        "name": "Aktuelle Wirkleistung",
        "unit": "W",
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:lightning-bolt",
    },
}

# OBIS codes that are energy values (werden als Raw + Skaliert bereitgestellt)
ENERGY_OBIS_CODES = {"1.8.0", "1.8.1", "1.8.2", "2.8.0", "2.8.1", "2.8.2"}
