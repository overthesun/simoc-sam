import time
import importlib

from unittest.mock import patch

import pytest

from simoc_sam import config
from simoc_sam.sensors import basesensor

READING = dict(co2=100, hum=50, temp=25)
INFO = {
    'co2': dict(label='CO2', unit='ppm'),
    'temp': dict(label='Temperature', unit='°C'),
    'rel_hum': dict(label='Relative Humidity', unit='%'),
}
class MySensor(basesensor.BaseSensor):
    sensor_type = 'TestSensor'
    reading_info = INFO
    def read_sensor_data(self):
        self.print_reading(READING)
        return dict(READING)

@pytest.fixture
def sensor():
    yield MySensor()

@pytest.fixture
def wrapper(sensor):
    return basesensor.MQTTWrapper(sensor, read_delay=0)

@pytest.fixture
def mock_print(wrapper):
    with patch.object(wrapper, 'print') as mock_print:
        yield mock_print

@pytest.fixture(autouse=True)
def reload_basesensor():
    # the logpath depends on config.location and hostname
    importlib.reload(config)
    importlib.reload(basesensor)
    yield

@pytest.fixture(autouse=True)
def mock_paho_client():
    with patch('paho.mqtt.client.Client', autospec=True) as mock_client:
        yield mock_client


# BaseSensor tests

def test_abstract_method():
    # this should fail if read_sensor_data is not implemented
    class BrokenSensorSubclass(basesensor.BaseSensor):
        pass
    with pytest.raises(TypeError):
        s = BrokenSensorSubclass()

def test_context_manager():
    with MySensor() as sensor:
        assert isinstance(sensor, MySensor)

def test_name_type():
    with MySensor(name='HAL 9000') as sensor:
        assert sensor.sensor_type == 'TestSensor'
        assert sensor.sensor_name == 'HAL 9000'

def test_log_path(sensor):
    assert str(sensor.log_path).endswith('/testhost_testhost1_TestSensor.jsonl')

def test_iter_readings(sensor):
    # check that iter_readings() yields values returned by read_sensor_data()
    assert sensor.read_sensor_data() == READING
    readings = list(sensor.iter_readings(delay=0, n=5, add_timestamp=False,
                                         add_n=False))
    assert readings == [READING]*5
    # check that the n arg works
    assert len(list(sensor.iter_readings(delay=0, n=1))) == 1
    assert len(list(sensor.iter_readings(delay=0, n=10))) == 10
    for x, r in enumerate(sensor.iter_readings(delay=0, n=0)):
        assert isinstance(r, dict)
        assert len(r) == 5
        if x > 10:
            break
    # check that add_timestamp and add_n work
    assert all('timestamp' in r and 'n' in r
               for r in sensor.iter_readings(delay=0, n=5))
    assert all('timestamp' in r and 'n' not in r
               for r in sensor.iter_readings(delay=0, n=5, add_n=False))
    assert all('timestamp' not in r and 'n' in r
               for r in sensor.iter_readings(delay=0, n=5, add_timestamp=False))

def test_reading_delay(sensor):
    ts = time.time()
    readings = list(sensor.iter_readings(delay=0, n=3))
    te = time.time()
    assert te-ts < 0.1
    ts = time.time()
    readings = list(sensor.iter_readings(delay=0.1, n=3))
    te = time.time()
    assert te-ts > 0.1

def test_reading_num(sensor):
    assert sensor.reading_num == 0
    readings = list(sensor.iter_readings(delay=0, n=1))
    assert sensor.reading_num == 1
    readings = list(sensor.iter_readings(delay=0, n=4))
    assert sensor.reading_num == 5
    readings = list(sensor.iter_readings(delay=0, n=5))
    assert sensor.reading_num == 10

def test_log(sensor, tmp_path):
    payload = '{"foo": 1}'
    sensor.log_path = tmp_path / "testlog.jsonl"
    sensor.log(payload)
    with open(sensor.log_path) as f:
        lines = f.readlines()
    assert lines[-1].strip() == payload
    # test for nonexisting file
    sensor.log_path = "/nonexistent/path/testlog.jsonl"
    # Patch sensor.print to check error message
    from unittest.mock import patch
    with patch.object(sensor, 'print') as mock_print:
        sensor.log(payload)
        mock_print.assert_called_once()
        assert '/nonexistent/path/testlog.jsonl' in str(mock_print.call_args[0][0])

def test_print_reading(sensor):
    with patch.object(sensor, 'print') as mock_print:
        sensor.print_reading(READING)
        mock_print.assert_called_once()

def test_iter_readings_logs(sensor, monkeypatch):
    from simoc_sam import config
    # Test with logging enabled
    monkeypatch.setattr(config, "enable_jsonl_logging", True)
    with patch.object(sensor, 'log') as mock_log:
        readings = list(sensor.iter_readings(delay=0, n=3))
        assert mock_log.call_count == 3
    # Test with logging disabled
    monkeypatch.setattr(config, "enable_jsonl_logging", False)
    with patch.object(sensor, 'log') as mock_log:
        readings = list(sensor.iter_readings(delay=0, n=3))
        mock_log.assert_not_called()


# MQTTWrapper tests

def test_mqttwrapper_init(sensor):
    # test with custom args
    wrapper = basesensor.MQTTWrapper(sensor, read_delay=10, verbose=True)
    assert wrapper.sensor is sensor
    assert wrapper.read_delay == 10
    assert wrapper.verbose is True
    assert wrapper.topic == f'testhost/testhost1/{sensor.sensor_name}'

def test_mqttwrapper_connect_start_stop(wrapper):
    mqttc = wrapper.mqttc
    wrapper.connect('localhost', 1883)
    mqttc.connect.assert_called_with('localhost', 1883)
    wrapper.start('localhost', 1883)
    mqttc.loop_start.assert_called_once()
    mqttc.connect.assert_called_with('localhost', 1883)
    wrapper.stop()
    mqttc.loop_stop.assert_called_once()

def test_mqttwrapper_on_connect_and_disconnect(wrapper, mock_print):
    wrapper.verbose = True
    wrapper.on_connect(None, None, None, 0)
    mock_print.assert_any_call("Connected to MQTT broker")
    wrapper.on_connect(None, None, None, 1)
    mock_print.assert_any_call("Connection failed with code 1")
    wrapper.on_disconnect(None, None, None)
    mock_print.assert_any_call("Disconnected from MQTT broker")

def test_mqttwrapper_send_data(wrapper, mock_print):
    mqttc = wrapper.mqttc
    wrapper.send_data(n=2)
    assert mqttc.publish.call_count == 2
    for call in mqttc.publish.call_args_list:
        assert call.kwargs['payload'] is not None
        assert call.args[0] == wrapper.topic
    assert mock_print.call_count >= 2

def test_mqttwrapper_send_data_publish_error(wrapper, mock_print):
    mqttc = wrapper.mqttc
    mqttc.publish.side_effect = RuntimeError("fail")
    wrapper.send_data(n=1)
    mock_print.assert_any_call('No longer connected to the server (fail)...')
