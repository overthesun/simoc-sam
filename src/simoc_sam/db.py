"""SQLite database initialization and query helpers."""

import sqlite3

from simoc_sam.sensors.utils import SENSOR_DATA

_PYTHON_TO_SQL = {'float': 'REAL', 'int': 'INTEGER', 'str': 'TEXT'}


def init_db(db_path):
    """Open the SQLite DB and create one table per sensor type."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')  # for safe concurrent reads
    for sensor_name, sensor_data in SENSOR_DATA.items():
        field_defs = []
        for fname, finfo in sensor_data.data.items():
            sql_type = _PYTHON_TO_SQL.get(finfo.get('type', 'float'), 'REAL')
            field_defs.append(f'{fname} {sql_type}')
        conn.execute(f'''
            CREATE TABLE IF NOT EXISTS {sensor_name} (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                location  TEXT NOT NULL,
                host      TEXT NOT NULL,
                n         INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                {", ".join(field_defs)}
            )
        ''')
        conn.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_{sensor_name}_sensor_id_ts
            ON {sensor_name} (sensor_id, timestamp)
        ''')
    conn.commit()
    return conn


def get_readings(conn, sensor, *, sensor_id=None, location=None, host=None,
                 start=None, end=None, decimate=None):
    """Query sensor readings and return them in columnar format.

    Args:
        conn:      open SQLite connection
        sensor:    sensor table name, e.g. 'scd30'
        sensor_id: filter by exact sensor_id, e.g. 'lab.rpi1.scd30'
        location:  filter by location
        host:      filter by host
        start:     filter timestamp >= start (ISO string, e.g. '2026-01-01', inclusive)
        end:       filter timestamp < end (ISO string, exclusive)
        decimate:  if set, return ~this many evenly-spaced rows

    Returns:
        dict of column -> list, e.g.:
        {'n': [...], 'timestamp': [...], 'co2': [...], 'temperature': [...]}
        Returns an empty dict if no rows match.
    """
    if sensor not in SENSOR_DATA:
        raise ValueError(f'Unknown sensor: {sensor!r}')
    conditions, params = [], []
    if sensor_id:
        conditions.append('sensor_id = ?')
        params.append(sensor_id)
    if location:
        conditions.append('location = ?')
        params.append(location)
    if host:
        conditions.append('host = ?')
        params.append(host)
    if start:
        conditions.append('timestamp >= ?')
        params.append(start)
    if end:
        conditions.append('timestamp < ?')
        params.append(end)
    where = f'WHERE {" AND ".join(conditions)}' if conditions else ''
    cursor = conn.execute(
        f'SELECT * FROM {sensor} {where} ORDER BY timestamp', params
    )
    col_names = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    if not rows:
        return {}
    if decimate and len(rows) > decimate:
        step = len(rows) / decimate
        rows = [rows[int(i * step)] for i in range(decimate)]
    return {
        col: [row[i] for row in rows]
        for i, col in enumerate(col_names)
        if col != 'id'
    }


def get_sensor_ids(conn, sensor=None):
    """Return a sorted list of distinct sensor_ids present in the DB.

    Args:
        sensor: if given, query only that sensor's table; otherwise
                aggregate across all sensor tables.
    """
    if sensor is not None:
        if sensor not in SENSOR_DATA:
            raise ValueError(f'Unknown sensor: {sensor!r}')
        rows = conn.execute(
            f'SELECT DISTINCT sensor_id FROM {sensor}'
        ).fetchall()
        return sorted(row[0] for row in rows)
    ids = set()
    for sensor_name in SENSOR_DATA:
        rows = conn.execute(
            f'SELECT DISTINCT sensor_id FROM {sensor_name}'
        ).fetchall()
        ids.update(row[0] for row in rows)
    return sorted(ids)
