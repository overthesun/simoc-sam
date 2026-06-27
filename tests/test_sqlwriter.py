import json
from unittest import mock

import pytest

from simoc_sam import sqlwriter


@pytest.fixture
def mock_msg():
    payload = json.dumps(dict(n=0, timestamp='2024-03-06 12:00:00',
                              co2=450.0, temperature=23.5, humidity=45.2))
    return mock.Mock(payload=payload.encode('utf-8'), topic='sam/testhost/scd30')


def test_on_message_inserts_row(mock_msg, db_conn):
    sqlwriter.on_message(client=None, userdata=None, msg=mock_msg)
    row = db_conn.execute(
        'SELECT sensor_id, location, host, n, timestamp, co2, temperature, humidity FROM scd30'
    ).fetchone()
    assert row == ('sam.testhost.scd30', 'sam', 'testhost', 0,
                   '2024-03-06 12:00:00', 450.0, 23.5, 45.2)


@pytest.mark.parametrize('payload, topic', [
    (b'invalid json', 'sam/testhost/scd30'),
    (b'{"n": 0}', 'invalid/topic'),
    (b'{"n": 0}', 'sam/testhost/unknown_sensor'),
], ids=['invalid_json', 'invalid_topic', 'unknown_sensor'])
def test_invalid_message_skipped(payload, topic, db_conn):
    msg = mock.Mock(payload=payload, topic=topic)
    sqlwriter.on_message(client=None, userdata=None, msg=msg)
    count = db_conn.execute('SELECT COUNT(*) FROM scd30').fetchone()[0]
    assert count == 0


def test_subscribe_on_connect(monkeypatch):
    monkeypatch.setattr('simoc_sam.config.mqtt_topic_sub', 'sam/#')
    client = mock.MagicMock()
    sqlwriter.on_connect(client, None, None, 0)
    client.subscribe.assert_called_once_with('sam/#')


def test_main_creates_data_dir(tmp_path, monkeypatch):
    db_dir = tmp_path / 'newdir'
    monkeypatch.setattr('simoc_sam.config.db_path', db_dir / 'test.db')
    monkeypatch.setattr('simoc_sam.config.mqtt_host', 'localhost')
    monkeypatch.setattr('simoc_sam.config.mqtt_port', 1883)
    mock_client = mock.MagicMock()
    mock_client.loop_forever.side_effect = KeyboardInterrupt
    with mock.patch('paho.mqtt.client.Client', return_value=mock_client):
        sqlwriter.main()
    assert db_dir.exists()
    assert (db_dir / 'test.db').exists()
