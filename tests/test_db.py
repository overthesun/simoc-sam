import pytest

from simoc_sam.db import init_db, get_readings, get_sensor_ids
from simoc_sam.sensors.utils import SENSOR_DATA


@pytest.fixture
def db(tmp_path):
    conn = init_db(tmp_path / 'test.db')
    yield conn
    conn.close()


def _insert_row(conn, sensor, *, location='lab', host='rpi1', n=0,
                timestamp='2026-01-15 12:00:00', **kwargs):
    sensor_id = f'{location}.{host}.{sensor}'
    row = {'sensor_id': sensor_id, 'location': location, 'host': host,
           'n': n, 'timestamp': timestamp, **kwargs}
    cols = ', '.join(row.keys())
    placeholders = ', '.join('?' * len(row))
    conn.execute(
        f'INSERT INTO {sensor} ({cols}) VALUES ({placeholders})',
        list(row.values()),
    )
    conn.commit()


# --- init_db ---

def test_init_db_creates_tables(db):
    tables = {row[0] for row in
              db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for sensor_name in SENSOR_DATA:
        assert sensor_name in tables


def test_init_db_field_types(db):
    bno_cols = {row[1]: row[2] for row in db.execute('PRAGMA table_info(bno085)')}
    assert bno_cols['raw_accel_x'] == 'INTEGER'
    assert bno_cols['stability_classification'] == 'TEXT'
    assert bno_cols['shake'] == 'INTEGER'
    scd_cols = {row[1]: row[2] for row in db.execute('PRAGMA table_info(scd30)')}
    assert scd_cols['co2'] == 'REAL'
    assert scd_cols['temperature'] == 'REAL'


# --- get_readings ---

def test_get_readings_columnar_format(db):
    _insert_row(db, 'scd30', co2=450.0, temperature=23.5, humidity=45.2)
    result = get_readings(db, 'scd30')
    assert result['co2'] == [450.0]
    assert result['temperature'] == [23.5]
    assert result['humidity'] == [45.2]
    assert result['n'] == [0]
    assert 'id' not in result


def test_get_readings_empty(db):
    assert get_readings(db, 'scd30') == {}


def test_get_readings_unknown_sensor(db):
    with pytest.raises(ValueError):
        get_readings(db, 'nonexistent')


def test_get_readings_filter_by_location(db):
    _insert_row(db, 'scd30', location='lab', co2=450.0, temperature=23.5, humidity=45.2)
    _insert_row(db, 'scd30', location='office', co2=500.0, temperature=24.0, humidity=46.0)
    result = get_readings(db, 'scd30', location='lab')
    assert result['co2'] == [450.0]


def test_get_readings_filter_by_sensor_id(db):
    _insert_row(db, 'scd30', location='lab', host='rpi1', co2=450.0, temperature=23.5, humidity=45.2)
    _insert_row(db, 'scd30', location='lab', host='rpi2', co2=500.0, temperature=24.0, humidity=46.0)
    result = get_readings(db, 'scd30', sensor_id='lab.rpi1.scd30')
    assert result['co2'] == [450.0]


def test_get_readings_filter_by_time_range(db):
    _insert_row(db, 'scd30', n=0, timestamp='2026-01-10 12:00:00',
                co2=400.0, temperature=22.0, humidity=40.0)
    _insert_row(db, 'scd30', n=1, timestamp='2026-01-15 12:00:00',
                co2=450.0, temperature=23.0, humidity=45.0)
    _insert_row(db, 'scd30', n=2, timestamp='2026-01-20 12:00:00',
                co2=500.0, temperature=24.0, humidity=50.0)
    # start inclusive, end exclusive
    result = get_readings(db, 'scd30', start='2026-01-12', end='2026-01-18')
    assert result['co2'] == [450.0]


def test_get_readings_end_exclusive(db):
    """end is exclusive: 'give me January' = start='2026-01-01', end='2026-02-01'."""
    _insert_row(db, 'scd30', n=0, timestamp='2026-01-31 23:59:59',
                co2=450.0, temperature=23.0, humidity=45.0)
    _insert_row(db, 'scd30', n=1, timestamp='2026-02-01 00:00:00',
                co2=500.0, temperature=24.0, humidity=50.0)
    result = get_readings(db, 'scd30', start='2026-01-01', end='2026-02-01')
    assert result['co2'] == [450.0]  # Feb 1st excluded


def test_get_readings_decimate(db):
    for i in range(100):
        _insert_row(db, 'scd30', n=i,
                    timestamp=f'2026-01-{(i // 24) + 1:02d} {i % 24:02d}:00:00',
                    co2=float(400 + i), temperature=23.0, humidity=45.0)
    result = get_readings(db, 'scd30', decimate=10)
    assert len(result['co2']) == 10


# --- get_sensor_ids ---

def test_get_sensor_ids_for_sensor(db):
    _insert_row(db, 'scd30', location='lab', host='rpi1',
                co2=450.0, temperature=23.5, humidity=45.2)
    _insert_row(db, 'scd30', location='lab', host='rpi2',
                co2=460.0, temperature=24.0, humidity=46.0)
    ids = get_sensor_ids(db, 'scd30')
    assert ids == ['lab.rpi1.scd30', 'lab.rpi2.scd30']


def test_get_sensor_ids_all(db):
    _insert_row(db, 'scd30', location='lab', host='rpi1',
                co2=450.0, temperature=23.5, humidity=45.2)
    _insert_row(db, 'bme688', location='lab', host='rpi1',
                temperature=23.5, pressure=1013.0, humidity=45.0,
                gas_resistance=100000.0, altitude=500.0)
    ids = get_sensor_ids(db)
    assert 'lab.rpi1.scd30' in ids
    assert 'lab.rpi1.bme688' in ids


def test_get_sensor_ids_unknown_raises(db):
    with pytest.raises(ValueError):
        get_sensor_ids(db, 'nonexistent')
