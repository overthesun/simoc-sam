import time

from unittest.mock import AsyncMock, ANY

import pytest

from simoc_sam.sensors.basesensor import BaseSensor, SIOWrapper


READING = dict(co2=100, hum=50, temp=25)
INFO = {
    'co2': dict(label='CO2', unit='ppm'),
    'temp': dict(label='Temperature', unit='°C'),
    'rel_hum': dict(label='Relative Humidity', unit='%'),
}
class MySensor(BaseSensor):
    sensor_type = 'TestSensor'
    reading_info = INFO
    def read_sensor_data(self):
        return dict(READING)

@pytest.fixture
def sensor():
    yield MySensor()

def test_abstract_method():
    # this should fail if read_sensor_data is not implemented
    class BrokenSensorSubclass(BaseSensor):
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


# SIOWrapper tests
@pytest.mark.asyncio
async def test_siowrapper(sensor):
    siowrapper = SIOWrapper(sensor, read_delay=0)
    # mock the socketio.AsyncClient instance
    siowrapper.sio = sio_ac = AsyncMock(spec=siowrapper.sio)
    # start the client and check it connects to the server
    await siowrapper.start(8081)
    sio_ac.connect.assert_awaited_with('http://localhost:8081')
    # check that sensor registers itself on connect
    await siowrapper.connect()
    sensor_info = {'sensor_type': 'TestSensor', 'sensor_name': None,
                   'sensor_id': None, 'sensor_desc': None,
                    'reading_info': INFO}
    sio_ac.emit.assert_awaited_with('register-sensor', sensor_info)
    # request 2 readings and check that at least a reading has been sent
    await siowrapper.send_data(n=2)
    sio_ac.emit.assert_awaited_with('sensor-reading', ANY)
    # check emitted events
    calls = sio_ac.emit.await_args_list
    assert len(calls) == 3
    expected_events = ['register-sensor', 'sensor-reading', 'sensor-reading']
    assert [c.args[0] for c in calls] == expected_events
