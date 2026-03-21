import json

from pathlib import Path
from unittest import mock

import pytest

from simoc_sam import csvwriter


@pytest.fixture
def mock_mqtt_client(monkeypatch):
    client = mock.MagicMock()
    monkeypatch.setattr('paho.mqtt.client.Client',
                        lambda *args, **kwargs: client)
    yield client

@pytest.fixture
def mock_config(monkeypatch):
    """Mock the config module with test values"""
    monkeypatch.setattr('simoc_sam.config.mqtt_host', 'mock_host')
    monkeypatch.setattr('simoc_sam.config.mqtt_port', 1234)
    monkeypatch.setattr('simoc_sam.config.mqtt_topic_sub', 'sam/#')

@pytest.fixture
def mock_open(monkeypatch):
    m = mock.mock_open()
    monkeypatch.setattr('builtins.open', m)
    yield m

@pytest.fixture
def mock_msg():
    payload = json.dumps(dict(n=0, timestamp='2024-03-06 12:00:00', co2=123))
    yield mock.Mock(payload=payload.encode('utf-8'), topic='sam/test/scd30')



def test_subscribe_on_connect(mock_mqtt_client, mock_config):
    # on_connect now reads topic from config
    csvwriter.on_connect(mock_mqtt_client, None, None, 0)
    mock_mqtt_client.subscribe.assert_called_once_with('sam/#')

def test_on_message(mock_open, mock_msg):
    # mock tell to return 0 (empty file)
    mock_open.return_value.tell.return_value = 0
    csvwriter.on_message(client=None, userdata=None, msg=mock_msg)
    csv_path = Path.home() / 'data' / 'sam_test_scd30.csv'
    mock_open.assert_called_with(csv_path, 'a', newline='')
    handle = mock_open()
    assert handle.write.call_count == 2
    calls = [
        mock.call('n,timestamp,co2,temperature,humidity\r\n'),  # adds the header
        mock.call('0,2024-03-06 12:00:00,123,,\r\n'),  # and the readings
    ]
    handle.write.assert_has_calls(calls)
    # now mock tell to return > 0 (file has content)
    mock_open.return_value.tell.return_value = 100
    csvwriter.on_message(client=None, userdata=None, msg=mock_msg)
    calls.append(mock.call('0,2024-03-06 12:00:00,123,,\r\n'))  # readings only
    assert handle.write.call_count == 3
    handle.write.assert_has_calls(calls)

@pytest.mark.parametrize(
    "payload, topic",
    [(b'invalid json', 'sam/test/scd30'),
     (b'{"n": 0}', 'invalid/topic'),
     (b'{"n": 0}', 'sam/test/unknown')],
    ids=["invalid_json", "invalid_topic", "invalid_sensor"],
)
def test_invalid_message(mock_open, payload, topic):
    msg = mock.Mock(payload=payload, topic=topic)
    csvwriter.on_message(client=None, userdata=None, msg=msg)
    mock_open.assert_not_called()


def test_main(mock_mqtt_client, mock_config, monkeypatch):
    csvwriter.main()
    mock_mqtt_client.connect.assert_called_once_with('mock_host', 1234)
    assert mock_mqtt_client.loop_forever.called

def test_main_custom_topic(mock_mqtt_client, monkeypatch):
    # Test with a different config topic
    monkeypatch.setattr('simoc_sam.config.mqtt_host', 'test_host')
    monkeypatch.setattr('simoc_sam.config.mqtt_port', 5678)
    monkeypatch.setattr('simoc_sam.config.mqtt_topic_sub', 'custom/topic')
    csvwriter.main()
    # Verify connection uses custom config
    mock_mqtt_client.connect.assert_called_once_with('test_host', 5678)
    # Verify subscription happens in on_connect with custom topic
    csvwriter.on_connect(mock_mqtt_client, None, None, 0)
    mock_mqtt_client.subscribe.assert_called_with('custom/topic')
