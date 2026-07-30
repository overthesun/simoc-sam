"""SQLite database initialization and query helpers."""

import sqlite3

from simoc_sam.sensors.utils import SENSOR_DATA

_PYTHON_TO_SQL = {'float': 'REAL', 'int': 'INTEGER', 'str': 'TEXT'}

_conn = None  # module-level cached connection


def connect(db_path=None, verbose=False):
    """Open and return a new connection to the db."""
    if db_path is None:
        from simoc_sam import config
        db_path = config.db_path
    if verbose:
        print(f'Opening SQLite database: {db_path}')
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')  # for safe concurrent reads
    return conn


def init_db(db_path=None, verbose=True):
    """Open the SQLite DB and create one table per sensor type.

    If db_path is not given, uses config.db_path.
    Caches the connection to the module-level variable _conn.
    Returns the open connection.
    """
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
    conn = connect(db_path, verbose=verbose)
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
    _conn = conn
    return conn


def get_conn(db_path=None):
    """Return the cached connection, opening it if needed."""
    if _conn is None:
        return init_db(db_path)
    return _conn


def close_db(conn=None):
    """Close the given connection (or the cached one if not provided)."""
    global _conn
    if conn is None or conn is _conn:
        if _conn is not None:
            _conn.close()
            _conn = None
    else:
        conn.close()


def get_readings(sensor, *, conn=None, sensor_id=None, location=None, host=None,
                 start=None, end=None, decimate=None):
    """Query sensor readings and return them in columnar format.

    Args:
        sensor:    sensor table name, e.g. 'scd30'
        conn:      open SQLite connection (uses cached connection if omitted)
        sensor_id: filter by exact sensor_id, e.g. 'lab.rpi1.scd30'
        location:  filter by location
        host:      filter by host
        start:     filter timestamp >= start (ISO string, e.g. '2026-01-01T00:00:00+00:00', inclusive)
        end:       filter timestamp < end (ISO string, exclusive)
        decimate:  if set, return ~this many evenly-spaced rows

    Returns:
        dict of column -> list, e.g.:
        {'n': [...], 'timestamp': [...], 'co2': [...], 'temperature': [...]}
        Returns an empty dict if no rows match.
    """
    if conn is None:
        conn = get_conn()
    if sensor not in SENSOR_DATA:
        raise ValueError(f'Unknown sensor: {sensor!r}')
    if decimate is not None and decimate <= 0:
        raise ValueError(f'decimate must be a positive integer, got {decimate!r}')
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
    # Interpolates sensor (validated against SENSOR_DATA above); all other
    # values use parameterized queries to prevent SQL injection.
    full_sql = f'SELECT * FROM {sensor} {where} ORDER BY timestamp'
    if decimate:
        # Two O(log N) index seeks give the rowid range of matching rows.
        # Fast when WHERE uses an indexed column (e.g. sensor_id).
        # Assumes rows are inserted in timestamp order so the id range
        # corresponds to the timestamp range.
        boundary_sql = f'SELECT id FROM {sensor} {where} ORDER BY timestamp'
        first_row = conn.execute(f'{boundary_sql} ASC LIMIT 1', params).fetchone()
        if first_row is None:
            return {}
        last_row = conn.execute(f'{boundary_sql} DESC LIMIT 1', params).fetchone()
        first_id, last_id = first_row[0], last_row[0]
        if last_id - first_id < decimate:
            # Fewer candidate rows than target; return all matching rows.
            cursor = conn.execute(full_sql, params)
        else:
            # Evenly-spaced rowid targets spanning first_id..last_id inclusive.
            # Integer linspace: target[i] = first + (last-first)*i//(n-1).
            target_ids = [first_id + (last_id - first_id) * i // ((decimate - 1) or 1)
                          for i in range(decimate)]
            id_placeholders = ','.join('?' * len(target_ids))
            extra = f' AND {" AND ".join(conditions)}' if conditions else ''
            cursor = conn.execute(
                f'SELECT * FROM {sensor} WHERE id IN ({id_placeholders}){extra} ORDER BY id',
                [*target_ids, *params]
            )
    else:
        cursor = conn.execute(full_sql, params)
    col_names = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    if not rows:
        return {}
    return {
        col: [row[i] for row in rows]
        for i, col in enumerate(col_names)
        if col != 'id'
    }


def get_sensor_ids(sensor=None, *, conn=None):
    """Return a sorted list of distinct sensor_ids present in the DB.

    Args:
        sensor: if given, query only that sensor's table; otherwise
                aggregate across all sensor tables.
        conn:   open SQLite connection (uses cached connection if omitted)
    """
    if conn is None:
        conn = get_conn()
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
