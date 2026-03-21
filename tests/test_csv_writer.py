import json

from pathlib import Path
from unittest import mock

import pytest

from simoc_sam import csv_writer


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
def mock_size(monkeypatch):
    size_mock = mock.Mock(st_size=0)
    monkeypatch.setattr('os.stat', lambda *args, **kwargs: size_mock)
    yield size_mock

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
    csv_writer.on_connect(mock_mqtt_client, None, None, 0)
    mock_mqtt_client.subscribe.assert_called_once_with('sam/#')

def test_on_message(mock_size, mock_open, mock_msg):
    csv_writer.on_message(client=None, userdata=None, msg=mock_msg)
    csv_path = Path.home() / 'data' / 'sam_test_scd30.csv'
    mock_open.assert_called_with(csv_path, 'a', newline='')
    handle = mock_open()
    assert handle.write.call_count == 2
    calls = [
        mock.call('n,timestamp,co2,temperature,humidity\r\n'),  # adds the header
        mock.call('0,2024-03-06 12:00:00,123,,\r\n'),  # and the readings
    ]
    handle.write.assert_has_calls(calls)
    mock_size.st_size = 100  # now the file exists and has the header
    csv_writer.on_message(client=None, userdata=None, msg=mock_msg)
    calls.append(mock.call('0,2024-03-06 12:00:00,123,,\r\n'))  # readings only
    assert handle.write.call_count == 3
    handle.write.assert_has_calls(calls)

def test_main(mock_mqtt_client, mock_config, monkeypatch):
    csv_writer.main()
    mock_mqtt_client.connect.assert_called_once_with('mock_host', 1234)
    assert mock_mqtt_client.loop_forever.called

def test_main_custom_topic(mock_mqtt_client, monkeypatch):
    # Test with a different config topic
    monkeypatch.setattr('simoc_sam.config.mqtt_host', 'test_host')
    monkeypatch.setattr('simoc_sam.config.mqtt_port', 5678)
    monkeypatch.setattr('simoc_sam.config.mqtt_topic_sub', 'custom/topic')
    csv_writer.main()
    # Verify connection uses custom config
    mock_mqtt_client.connect.assert_called_once_with('test_host', 5678)
    # Verify subscription happens in on_connect with custom topic
    csv_writer.on_connect(mock_mqtt_client, None, None, 0)
    mock_mqtt_client.subscribe.assert_called_with('custom/topic')

def test_main_default_config(mock_mqtt_client, mock_config):
    # Test with default mock config
    csv_writer.main()
    mock_mqtt_client.connect.assert_called_once_with('mock_host', 1234)
