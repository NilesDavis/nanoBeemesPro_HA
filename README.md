# nanoBeemesPro Reader – Home Assistant Integration

Custom Integration für den **BSED nanoBeemesPro** Lesekopf (auch bekannt als We Share Energy Lesekopf).

Liest Daten lokal über `http://<IP>/emeter.json` – kein Cloud-Abo erforderlich.

## Sensoren

| Sensor | OBIS | Einheit |
|---|---|---|
| Aktuelle Wirkleistung | 16.7.0 | W |
| Einspeisung (effektiv) | – | W |
| Entnahme (effektiv) | – | W |
| 16.7.0 - Einspeisung (Rohdaten) | 16.7.0 | W |
| 16.7.0 - Entnahme (Rohdaten) | 16.7.0 | W |
| Wirkenergie Bezug gesamt | 1.8.0 | kWh |
| Wirkenergie Bezug Tarif 1 | 1.8.1 | kWh |
| Wirkenergie Bezug Tarif 2 | 1.8.2 | kWh |
| Wirkenergie Einspeisung gesamt | 2.8.0 | kWh |
| Wirkenergie Einspeisung Tarif 1 | 2.8.1 | kWh |
| Wirkenergie Einspeisung Tarif 2 | 2.8.2 | kWh |
| Zählernummer | – | – |

Die Leistung (16.7.0) ist negativ bei Einspeisung (PV-Überschuss).

### Richtungs-Sensoren (Einspeisung / Entnahme)

Ab Version 1.4.0 werden aus der Wirkleistung zusätzlich zwei getrennte Richtungs-Sensoren
abgeleitet (jeweils ≥ 0 W):

- **Einspeisung** und **Entnahme (effektiv):** Die effektive Wirkleistung (echter 16.7.0
  wenn verfügbar, sonst Delta-Schätzung aus 1.8.0/2.8.0) wird in die beiden Richtungen
  aufgeteilt. Damit funktionieren diese Sensoren auch an Zählern, die 16.7.0 nicht liefern
  (z.B. EMH mit `emstatus:1`).
- **16.7.0 - Einspeisung/Entnahme (Rohdaten):** Split aus dem rohen 16.7.0-Zählerwert
  (ohne `power_factor`-Skalierung). Bleiben `unknown`, wenn der Zähler 16.7.0 nicht liefert.

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
