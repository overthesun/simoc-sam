import time
import pytest

from basesensor import BaseSensor


READING = dict(co2=100, hum=50, temp=25)
class MySensor(BaseSensor):
    def read_sensor_data(self):
        return dict(READING)


def test_abstract_method():
    # this should fail if read_sensor_data is not implemented
    class BrokenSensorSubclass(BaseSensor):
        pass
    with pytest.raises(TypeError):
        s = BrokenSensorSubclass()

def test_iter_readings():
    sensor = MySensor()
    # check that iter_readings() yields values returned by read_sensor_data()
    assert sensor.read_sensor_data() == READING
    readings = list(sensor.iter_readings(delay=0, n=5, add_timestamp=False,
                                         add_stepnum=False))
    assert readings == [READING]*5
    # check that the n arg works
    assert len(list(sensor.iter_readings(delay=0, n=1))) == 1
    assert len(list(sensor.iter_readings(delay=0, n=10))) == 10
    for x, r in enumerate(sensor.iter_readings(delay=0, n=0)):
        assert isinstance(r, dict)
        assert len(r) == 5
        if x > 10:
            break
    # check that add_timestamp and add_stepnum work
    assert all('timestamp' in r and 'step_num' in r
               for r in sensor.iter_readings(delay=0, n=5))
    assert all('timestamp' in r and 'step_num' not in r
               for r in sensor.iter_readings(delay=0, n=5, add_stepnum=False))
    assert all('timestamp' not in r and 'step_num' in r
               for r in sensor.iter_readings(delay=0, n=5, add_timestamp=False))

def test_reading_delay():
    sensor = MySensor()
    ts = time.time()
    readings = list(sensor.iter_readings(delay=0, n=3))
    te = time.time()
    assert te-ts < 0.1
    ts = time.time()
    readings = list(sensor.iter_readings(delay=0.1, n=3))
    te = time.time()
    assert te-ts > 0.1

def test_reading_num():
    sensor = MySensor()
    assert sensor.reading_num == 0
    readings = list(sensor.iter_readings(delay=0, n=1))
    assert sensor.reading_num == 1
    readings = list(sensor.iter_readings(delay=0, n=4))
    assert sensor.reading_num == 5
    readings = list(sensor.iter_readings(delay=0, n=5))
    assert sensor.reading_num == 10
