import json

from datetime import datetime, timezone, timedelta

import pytest

from simoc_sam.api import create_app, parse_timestamp, to_unix_ms


def make_timestamp(offset_seconds=0):
    """Return a UTC ISO timestamp offset from now by the given seconds."""
    dt = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return dt.isoformat(timespec='seconds')


def insert_row(conn, sensor, *, location='lab', host='rpi1', n=0,
               timestamp='2026-01-15T12:00:00+00:00', **kwargs):
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


@pytest.fixture
def client(tmp_path, db_conn):
    """Create a test client backed by an initialized temporary DB."""
    app = create_app(db_path=tmp_path / 'test.db')
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


# --- helpers ---

def test_parse_timestamp_aware():
    dt = parse_timestamp('2026-01-15T12:00:00+00:00')
    assert dt.tzinfo is not None
    assert dt.hour == 12

def test_parse_timestamp_naive_assumed_utc():
    dt = parse_timestamp('2026-01-15T12:00:00')
    assert dt.tzinfo == timezone.utc

def test_to_unix_ms():
    assert to_unix_ms('1970-01-01T00:00:01+00:00') == 1000


# --- /api/sensors ---

def test_sensors_lists_all_configured(client):
    data = client.get('/api/sensors').get_json()
    assert 'scd30' in data['sensors']
    assert 'bme688' in data['sensors']

def test_sensors_metric_metadata(client):
    data = client.get('/api/sensors').get_json()
    co2 = data['sensors']['scd30']['metrics']['co2']
    assert co2['label'] == 'CO2'
    assert co2['unit'] == 'ppm'

def test_sensors_inactive_when_empty(client):
    data = client.get('/api/sensors').get_json()
    assert all(not s['active'] for s in data['sensors'].values())

def test_sensors_no_has_data_when_empty(client):
    data = client.get('/api/sensors').get_json()
    assert all(not s['has_data'] for s in data['sensors'].values())

def test_sensors_has_data_true_with_any_data(client, db_conn):
    # even very old data counts
    insert_row(db_conn, 'scd30', timestamp=make_timestamp(-86400 * 30), co2=700)
    data = client.get('/api/sensors').get_json()
    assert data['sensors']['scd30']['has_data'] is True

def test_sensors_has_data_false_for_empty_sensor(client, db_conn):
    insert_row(db_conn, 'scd30', co2=700)
    data = client.get('/api/sensors').get_json()
    assert data['sensors']['bme688']['has_data'] is False

def test_sensors_tolerates_missing_table(tmp_path):
    """Sensors added to sensors.toml before sqlwriter runs have no table yet."""
    # open a DB with no tables at all
    app = create_app(db_path=tmp_path / 'empty.db')
    app.config['TESTING'] = True
    with app.test_client() as c:
        response = c.get('/api/sensors')
        assert response.status_code == 200
        data = response.get_json()
        assert all(not s['has_data'] for s in data['sensors'].values())

def test_latest_tolerates_missing_table(tmp_path):
    """api/latest returns empty sensors dict when no tables exist."""
    app = create_app(db_path=tmp_path / 'empty.db')
    app.config['TESTING'] = True
    with app.test_client() as c:
        response = c.get('/api/latest')
        assert response.status_code == 200
        assert response.get_json() == {'sensors': {}}

def test_sensors_active_with_recent_data(client, db_conn):
    insert_row(db_conn, 'scd30', timestamp=make_timestamp(), co2=700)
    data = client.get('/api/sensors').get_json()
    assert data['sensors']['scd30']['active'] is True

def test_sensors_inactive_with_old_data(client, db_conn):
    insert_row(db_conn, 'scd30', timestamp=make_timestamp(-3600), co2=700)
    data = client.get('/api/sensors').get_json()
    assert data['sensors']['scd30']['active'] is False


# --- /api/latest ---

def test_latest_empty_db(client):
    data = client.get('/api/latest').get_json()
    assert data == {'sensors': {}}

def test_latest_returns_most_recent(client, db_conn):
    insert_row(db_conn, 'scd30', n=0,
               timestamp='2026-01-15T12:00:00+00:00', co2=700)
    insert_row(db_conn, 'scd30', n=1,
               timestamp='2026-01-15T12:00:10+00:00', co2=710)
    data = client.get('/api/latest').get_json()
    reading = data['sensors']['scd30']
    assert reading['co2'] == 710
    assert reading['timestamp'] == '2026-01-15T12:00:10+00:00'
    assert reading['sensor_id'] == 'lab.rpi1.scd30'

def test_latest_skips_empty_sensors(client, db_conn):
    insert_row(db_conn, 'scd30', co2=700)
    data = client.get('/api/latest').get_json()
    assert 'scd30' in data['sensors']
    assert 'bme688' not in data['sensors']


# --- /api/query ---

def query(client, **kwargs):
    return client.post('/api/query', json=kwargs)

def test_query_missing_body(client):
    response = client.post('/api/query',
                           data='', content_type='application/json')
    assert response.status_code == 400

def test_query_missing_selection(client):
    assert query(client).status_code == 400

def test_query_unknown_sensor(client):
    response = query(client, selection={'nonexistent': ['co2']})
    assert response.status_code == 400
    assert 'nonexistent' in response.get_json()['error']

def test_query_unknown_metric(client):
    response = query(client, selection={'scd30': ['nonexistent']})
    assert response.status_code == 400

def test_query_invalid_limit(client):
    response = query(client, selection={'scd30': ['co2']}, limit=-5)
    assert response.status_code == 400

def test_query_empty_result(client):
    data = query(client, selection={'scd30': ['co2']}).get_json()
    assert data['count'] == 0
    assert data['scd30'] == {'timestamps': [], 'co2': []}

def test_query_returns_data(client, db_conn):
    insert_row(db_conn, 'scd30', n=0,
               timestamp='2026-01-15T12:00:00+00:00', co2=700, temperature=21.5)
    insert_row(db_conn, 'scd30', n=1,
               timestamp='2026-01-15T12:00:10+00:00', co2=710, temperature=21.6)
    data = query(client, selection={'scd30': ['co2']}).get_json()
    assert data['count'] == 2
    assert data['scd30']['co2'] == [700, 710]
    # timestamps are unix ms
    assert data['scd30']['timestamps'] == [
        to_unix_ms('2026-01-15T12:00:00+00:00'),
        to_unix_ms('2026-01-15T12:00:10+00:00'),
    ]
    # non-selected metrics are not included
    assert 'temperature' not in data['scd30']

def test_query_multiple_sensors(client, db_conn):
    insert_row(db_conn, 'scd30', co2=700)
    insert_row(db_conn, 'bme688', pressure=1013.2)
    data = query(client, selection={'scd30': ['co2'],
                                    'bme688': ['pressure']}).get_json()
    assert data['count'] == 2
    assert data['scd30']['co2'] == [700]
    assert data['bme688']['pressure'] == [1013.2]

def test_query_time_range(client, db_conn):
    for i in range(5):
        insert_row(db_conn, 'scd30', n=i,
                   timestamp=f'2026-01-15T12:00:0{i}+00:00', co2=700+i)
    data = query(client, selection={'scd30': ['co2']},
                 start='2026-01-15T12:00:01+00:00',
                 end='2026-01-15T12:00:04+00:00').get_json()
    # start inclusive, end exclusive
    assert data['scd30']['co2'] == [701, 702, 703]

def test_query_limit_decimates(client, db_conn):
    for i in range(10):
        insert_row(db_conn, 'scd30', n=i,
                   timestamp=f'2026-01-15T12:00:{i:02}+00:00', co2=700+i)
    data = query(client, selection={'scd30': ['co2']}, limit=5).get_json()
    assert len(data['scd30']['co2']) == 5


# --- /api/export ---

def export(client, **kwargs):
    return client.post('/api/export', json=kwargs)

def test_export_invalid_format(client):
    response = export(client, selection={'scd30': ['co2']}, format='xml')
    assert response.status_code == 400

def test_export_json(client, db_conn):
    insert_row(db_conn, 'scd30', co2=700)
    response = export(client, selection={'scd30': ['co2']}, format='json')
    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert 'attachment' in response.headers['Content-Disposition']
    data = json.loads(response.data)
    assert data['scd30']['co2'] == [700]

def test_export_csv(client, db_conn):
    insert_row(db_conn, 'scd30',
               timestamp='2026-01-15T12:00:00+00:00', co2=700)
    insert_row(db_conn, 'bme688',
               timestamp='2026-01-15T12:00:00+00:00', pressure=1013.2)
    response = export(client, selection={'scd30': ['co2'],
                                         'bme688': ['pressure']}, format='csv')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    lines = response.data.decode().strip().splitlines()
    assert lines[0] == 'sensor,timestamp,co2,pressure'
    assert 'scd30,2026-01-15T12:00:00+00:00,700.0,' in lines
    assert 'bme688,2026-01-15T12:00:00+00:00,,1013.2' in lines

def test_export_defaults_to_csv(client, db_conn):
    insert_row(db_conn, 'scd30', co2=700)
    response = export(client, selection={'scd30': ['co2']})
    assert response.mimetype == 'text/csv'

def test_export_no_decimation(client, db_conn):
    for i in range(10):
        insert_row(db_conn, 'scd30', n=i,
                   timestamp=f'2026-01-15T12:00:{i:02}+00:00', co2=700+i)
    response = export(client, selection={'scd30': ['co2']},
                      format='json', limit=5)
    data = json.loads(response.data)
    # limit is ignored by export
    assert len(data['scd30']['co2']) == 10
