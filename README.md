# nanoBeemesPro Reader – Home Assistant Integration

Custom Integration für den **BSED nanoBeemesPro** Lesekopf (auch bekannt als We Share Energy Lesekopf).

Liest Daten lokal über `http://<IP>/emeter.json` – kein Cloud-Abo erforderlich.

## Sensoren

| Sensor | OBIS | Einheit |
|---|---|---|
| Aktuelle Wirkleistung | 16.7.0 | W |
| Wirkenergie Bezug gesamt | 1.8.0 | kWh |
| Wirkenergie Bezug Tarif 1 | 1.8.1 | kWh |
| Wirkenergie Bezug Tarif 2 | 1.8.2 | kWh |
| Wirkenergie Einspeisung gesamt | 2.8.0 | kWh |
| Wirkenergie Einspeisung Tarif 1 | 2.8.1 | kWh |
| Wirkenergie Einspeisung Tarif 2 | 2.8.2 | kWh |
| Zählernummer | – | – |

Die Leistung (16.7.0) ist negativ bei Einspeisung (PV-Überschuss).

## Installation

1. Ordner `nanobeemespro_reader` in `<config>/custom_components/` kopieren
2. Home Assistant neu starten
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → "nanoBeemesPro Reader"**
4. IP-Adresse eingeben (z.B. `10.0.3.90`) und Abfrageintervall wählen (Standard: 5 Sek.)

## Energie-Dashboard

Die Sensoren `1.8.0` (Bezug) und `2.8.0` (Einspeisung) sind als `total_increasing` konfiguriert
und können direkt im HA Energie-Dashboard unter **Netz → Stromverbrauch / Rückspeisung** eingetragen werden.

## Anforderungen

- Home Assistant 2023.1 oder neuer
- Lesekopf im gleichen Netzwerk wie HA erreichbar
- Kein Abo, keine Cloud
