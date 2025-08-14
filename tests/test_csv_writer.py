import json

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
def mock_args(monkeypatch):
    mock_args = mock.Mock(host='mock_host', port=1234, topic='sam/#')
    csv_writer.args = mock_args
    yield mock_args
    del csv_writer.args

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
    yield mock.Mock(payload=payload.encode('utf-8'), topic='sam/test')



def test_subscribe_on_connect(mock_mqtt_client, mock_args):
    csv_writer.on_connect(mock_mqtt_client, None, None, 0)
    mock_mqtt_client.subscribe.assert_called_once_with('sam/#')

def test_on_message(mock_size, mock_open, mock_msg):
    csv_writer.on_message(client=None, userdata=None, msg=mock_msg)
    mock_open.assert_called_with('/home/sam/data/sam_test.csv', 'a', newline='')
    handle = mock_open()
    assert handle.write.call_count == 2
    calls = [
        mock.call('n,timestamp,co2\r\n'),  # adds the header
        mock.call('0,2024-03-06 12:00:00,123\r\n'),  # and the readings
    ]
    handle.write.assert_has_calls(calls)
    mock_size.st_size = 100  # now the file exists and has the header
    csv_writer.on_message(client=None, userdata=None, msg=mock_msg)
    calls.append(mock.call('0,2024-03-06 12:00:00,123\r\n'))  # readings only
    assert handle.write.call_count == 3
    handle.write.assert_has_calls(calls)

def test_main(mock_mqtt_client, mock_args, monkeypatch):
    csv_writer.main(mock_args.host, mock_args.port, mock_args.topic)
    print(mock_mqtt_client.connect.mock_calls)
    assert mock_mqtt_client.connect.called_with(mock_args.host, mock_args.port, 60)
    assert mock_mqtt_client.loop_forever.called

def test_main_custom_topic(mock_mqtt_client, mock_args):
    mock_args.topic = 'custom/topic'
    csv_writer.main(mock_args.host, mock_args.port, mock_args.topic)
    assert mock_mqtt_client.subscribe.called_with('custom/topic')

def test_main_default_topic(mock_mqtt_client, mock_args):
    csv_writer.main(mock_args.host, mock_args.port, mock_args.topic)
    assert mock_mqtt_client.subscribe.called_with('sam/#')

