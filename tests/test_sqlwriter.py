import json
from unittest import mock

import pytest

from simoc_sam import sqlwriter
from simoc_sam.db import init_db


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / 'test.db'


@pytest.fixture
def db_conn(db_path):
    conn = init_db(db_path)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def set_db_conn(db_conn):
    """Wire the module-level DB_CONN so on_message tests work."""
    sqlwriter.DB_CONN = db_conn
    yield
    sqlwriter.DB_CONN = None


@pytest.fixture
def mock_msg():
    payload = json.dumps(dict(n=0, timestamp='2024-03-06 12:00:00',
                              co2=450.0, temperature=23.5, humidity=45.2))
    return mock.Mock(payload=payload.encode('utf-8'), topic='sam/testhost/scd30')


def test_on_message_inserts_row(mock_msg):
    sqlwriter.on_message(client=None, userdata=None, msg=mock_msg)
    row = sqlwriter.DB_CONN.execute(
        'SELECT sensor_id, location, host, n, timestamp, co2, temperature, humidity FROM scd30'
    ).fetchone()
    assert row == ('sam.testhost.scd30', 'sam', 'testhost', 0,
                   '2024-03-06 12:00:00', 450.0, 23.5, 45.2)


@pytest.mark.parametrize('payload, topic', [
    (b'invalid json', 'sam/testhost/scd30'),
    (b'{"n": 0}', 'invalid/topic'),
    (b'{"n": 0}', 'sam/testhost/unknown_sensor'),
], ids=['invalid_json', 'invalid_topic', 'unknown_sensor'])
def test_invalid_message_skipped(payload, topic):
    msg = mock.Mock(payload=payload, topic=topic)
    sqlwriter.on_message(client=None, userdata=None, msg=msg)
    count = sqlwriter.DB_CONN.execute('SELECT COUNT(*) FROM scd30').fetchone()[0]
    assert count == 0


def test_subscribe_on_connect(monkeypatch):
    monkeypatch.setattr('simoc_sam.config.mqtt_topic_sub', 'sam/#')
    client = mock.MagicMock()
    sqlwriter.on_connect(client, None, None, 0)
    client.subscribe.assert_called_once_with('sam/#')


def test_main_creates_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / 'newdir'
    monkeypatch.setattr('simoc_sam.config.data_dir', data_dir)
    monkeypatch.setattr('simoc_sam.config.db_name', 'test.db')
    monkeypatch.setattr('simoc_sam.config.mqtt_host', 'localhost')
    monkeypatch.setattr('simoc_sam.config.mqtt_port', 1883)
    mock_client = mock.MagicMock()
    mock_client.loop_forever.side_effect = KeyboardInterrupt
    with mock.patch('paho.mqtt.client.Client', return_value=mock_client):
        sqlwriter.main()
    assert data_dir.exists()
    assert (data_dir / 'test.db').exists()
