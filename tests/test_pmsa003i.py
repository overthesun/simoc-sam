import sys
import types
from unittest.mock import Mock

from simoc_sam.sensors import pmsa003i, utils


def test_pmsa003i_reads_and_maps_sensor_data(monkeypatch):
    i2c = Mock()
    board = types.SimpleNamespace(I2C=Mock(return_value=i2c))
    monkeypatch.setattr(utils, 'import_board', lambda: board)
    monkeypatch.setattr(utils, 'import_busio', Mock())

    pm25_i2c = types.ModuleType('adafruit_pm25.i2c')
    pm25_i2c.PM25_I2C = Mock()
    pm25_package = types.ModuleType('adafruit_pm25')
    pm25_package.__path__ = []
    monkeypatch.setitem(sys.modules, 'adafruit_pm25', pm25_package)
    monkeypatch.setitem(sys.modules, 'adafruit_pm25.i2c', pm25_i2c)

    raw_reading = {
        'pm10 standard': 1,
        'pm25 standard': 2,
        'pm100 standard': 3,
        'pm10 env': 4,
        'pm25 env': 5,
        'pm100 env': 6,
        'particles 03um': 7,
        'particles 05um': 8,
        'particles 10um': 9,
        'particles 25um': 10,
        'particles 50um': 11,
        'particles 100um': 12,
    }
    pm25_i2c.PM25_I2C.return_value.read.return_value = raw_reading

    sensor = pmsa003i.PMSA003I()
    reading = sensor.read_sensor_data()

    pm25_i2c.PM25_I2C.assert_called_once_with(i2c)
    pm25_i2c.PM25_I2C.return_value.read.assert_called_once_with()
    assert reading == {
        'pm10_standard': 1,
        'pm25_standard': 2,
        'pm100_standard': 3,
        'pm10_environmental': 4,
        'pm25_environmental': 5,
        'pm100_environmental': 6,
        'particles_0_3um': 7,
        'particles_0_5um': 8,
        'particles_1_0um': 9,
        'particles_2_5um': 10,
        'particles_5_0um': 11,
        'particles_10um': 12,
    }
