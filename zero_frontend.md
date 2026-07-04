# Sensor UI (Pi Zero) — Final Architecture Plan

## Scope

A lightweight local-only monitoring UI for a single Raspberry Pi deployment.

Constraints:

* Single host system only
* Offline-first (no external runtime dependencies)
* Minimal maintenance overhead
* No frontend frameworks
* Fallback / diagnostic interface (not primary platform)

---

# Existing System

## MQTT ingestion (existing)

Sensors publish to:

```
location/host/sensor
```

Example payload:

```json
{
  "n": 123,
  "timestamp": "2026-06-27T19:04:06+00:00",
  "temperature": 21.4,
  "humidity": 44.1,
  "co2": 710
}
```

---

## SQLite Writer

Responsibilities:

* subscribes to MQTT topics
* parses sensor payloads
* writes append-only data into SQLite
* extracts:

  * `sensor_id` — composite key: `{location}.{host}.{sensor}` (e.g. `lab.rpi1.scd30`)
  * `location`, `host` — from MQTT topic
  * `n` — sensor sequence counter, from payload
  * `timestamp` — ISO string, from payload
  * metric values (wide schema)

This component is the sole writer to the database.
Holds a long-lived cached SQLite connection (`db._conn`).

---

# Database Model (assumed stable)

Append-only wide schema. **One table per sensor type** (e.g. `scd30`, `bme688`), named after the sensor key from `sensors.toml`.

Each row contains:

* `id` — autoincrement primary key
* `sensor_id` — composite: `{location}.{host}.{sensor}` (e.g. `lab.rpi1.scd30`)
* `location` — from MQTT topic
* `host` — from MQTT topic
* `n` — sensor sequence counter (from payload, not a row count)
* `timestamp` — UTC ISO 8601 string (e.g. `2026-06-27T19:04:06+00:00`)
* metric columns (e.g. `temperature`, `humidity`, `co2`)

Each table has a composite index on `(sensor_id, timestamp)`.

---

# Backend Architecture

## Components

### 1. SQLite Writer (existing)

MQTT → SQLite ingestion

### 2. Flask API (new, minimal)

Read-only interface to SQLite.

Opens its own dedicated connection via `db.connect()`, separate from the
sqlwriter's cached `_conn`. SQLite WAL mode (already enabled in `db.py`)
allows safe concurrent reads alongside the writer.

### 3. nginx (existing)

* serves static frontend
* proxies `/api/*` to Flask

---

## Request Flow

```
Browser
  ↓
nginx
  ↓
/ → static frontend
/api → Flask API
  ↓
SQLite
```

---

# Frontend

## Location

Top-level directory in the main repository:

```
simoc-sam/
  frontend/        ← new: static HTML, CSS, JS
    vendor/        ← vendored JS/CSS libraries
  src/
    simoc_sam/     ← existing Python; Flask API added here
  configs/         ← existing systemd service files
```

---

## Dependency Strategy

Libraries are stored directly in the repository (vendored):

```
frontend/vendor/chart.js
frontend/vendor/flatpickr.js
frontend/vendor/flatpickr.css
```

### Update mechanism

* versions are pinned; files are committed into the repo
* a script checks for upstream updates on a schedule (weekly or monthly)
  and opens a PR automatically if newer versions are available
* if Dependabot cannot handle vendored files, the script runs via GitHub Actions

### Pros

* fully offline at runtime
* no Node.js required on Pi
* predictable builds
* no CDN dependency
* simple deployment model

### Cons

* manual or scripted updates required for dependency bumps

### Modals

No additional library needed. The native HTML `<dialog>` element covers
OK / Yes / No prompts with minimal JS and CSS, and is supported in all
modern browsers.

---

# UI Structure

Three top-level sections, switchable via a navigation bar:

1. **Live Dashboard** — system health and current readings (default view)
2. **Historical Data** — time-range queries, plots, and tables
3. **Admin** (future) — configuration and maintenance

One section is active at a time.

---

## 1. Live Dashboard

Purpose:

* show system health
* display latest sensor readings

Features:

* list of sensors
* latest metric values per sensor
* timestamps
* auto-refresh via polling (1–10s)

---

## 2. Historical Data

Main analytical interface.

---

# Sensor + Metric Selection

Compact row layout: one row per sensor, with the sensor toggle on the left
followed by per-metric toggle buttons.

Important rule:

> Metrics are always selected within the context of a sensor.

Example:

```
[✓ SCD30 ]:  [✓ CO2]  [Temperature]  [✓ Humidity]
[  BME688]:  [Temperature]  [Pressure]
```

Deselecting the sensor toggle deselects all its metrics. This keeps the UI
compact and avoids deep vertical nesting on small screens.

---

# View Modes

Radio buttons:

* Plot
* Table

Only one active mode at a time.

No hybrid view.

---

# Time Range Selection

## Absolute range only

Two datetime pickers:

* start datetime
* end datetime

Implemented using:

flatpickr

---

# Export

Two buttons:

* Export visible selection
* Export full selection within time range

Formats:

* CSV
* JSON

Rules:

* exports reflect current UI filters
* no decimation applied

---

# Visualization

## Plot mode

* Chart.js
* one chart per selected sensor
* multiple metrics per sensor supported

No multi-sensor chart merging.

---

## Table mode

One table per sensor.

Structure:

```
timestamp | metric A | metric B | metric C
```

Rules:

* tables are per-sensor only
* reflects selected metrics
* no cross-sensor merging

---

# State Model

Frontend state:

```
selectedSensors
selectedMetricsPerSensor
timeRange (start, end)
viewMode
```

---

# API Design

## GET /api/sensors

Combines two sources:

* static config from `sensors.toml` via `SENSOR_DATA`: metric labels, units, sensor descriptions
* live DB query: which sensors have at least one row written within
  `max(10 minutes, sensor_read_delay)` — these are marked `"active": true`

Response example:

```json
{
  "sensors": {
    "scd30": {
      "name": "SCD-30",
      "active": true,
      "metrics": {
        "co2":         {"label": "CO2",         "unit": "ppm"},
        "temperature": {"label": "Temperature", "unit": "\u00b0C"},
        "humidity":    {"label": "Humidity",    "unit": "%"}
      }
    }
  }
}
```

---

## GET /api/latest

Returns latest values per sensor:

```json
{
  "sensors": {
    "scd30": {
      "temperature": 21.4,
      "humidity": 44.1,
      "co2": 710,
      "timestamp": "2026-06-27T19:04:06+00:00"
    }
  }
}
```

---

## POST /api/query

### Request

```json
{
  "start": "2026-06-27T00:00:00+00:00",
  "end": "2026-06-28T00:00:00+00:00",
  "selection": {
    "scd30": ["temperature", "co2"],
    "bme688": ["pressure"]
  },
  "limit": 1000
}
```

`limit` caps the number of rows returned per sensor (evenly spaced).
Omit `limit` to return all rows (used by export).

### Response

```json
{
  "count": 1200,
  "scd30": {
    "timestamps": [...],
    "temperature": [...],
    "co2": [...]
  },
  "bme688": {
    "timestamps": [...],
    "pressure": [...]
  }
}
```

Key rules:

* sensor-centric grouping
* metrics always nested under sensor
* includes `count` — total rows returned across all sensors
* `n` (sensor sequence counter) is excluded from responses unless explicitly requested

---

## POST /api/export

Same filters as `POST /api/query`.

Returns:

* CSV or JSON
* no downsampling
* respects UI selection

---

# nginx Configuration

```
/ → frontend
/api/* → Flask
```

---

# Testing

## Flask API

Unit tests using pytest + Flask test client.
Tests cover each endpoint with representative fixtures (mocked DB).

## Frontend

No automated tests for MVP.
Manual testing is sufficient for a minimal diagnostic interface.
Browser automation (e.g. Playwright) can be added later if needed.

---

# CI/CD Strategy

No build step — the frontend is static files committed directly to the repo.

## GitHub Actions

* run tests (Python / Flask API)
* check vendored JS dependencies for updates on a schedule (weekly or monthly);
  open a PR automatically if newer versions are available

## Deploy (Pi)

The `sam` CLI handles setup:

* `sam setup-frontend` — copies `frontend/` to `/var/www/simoc` and configures nginx
* `sam setup-flask` — installs and starts the Flask API systemd service

Fallback:

* `git pull` + restart services

---

# Admin Interface (future)

Not part of MVP.

Planned features:

* reset database
* rename host
* inspect sensors
* reload config

API namespace:

```
/api/admin/*
```

---

# Design Principles

Hard constraints:

* fully offline runtime
* single-host architecture
* no CDN dependency
* minimal moving parts
* sensor-centric data model

Preferred:

* polling instead of websockets
* explicit state-driven UI
* wide-table optimized queries
* simple API contracts

Avoid:

* frontend frameworks
* cross-sensor table merging
* runtime dependency downloads
* over-engineered abstractions
