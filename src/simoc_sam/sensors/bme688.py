"""Driver for the BME688 Temp/Humidity/Pressure/Gas Resistance sensor."""
from . import utils
from .basesensor import BaseSensor

board = utils.import_board()
import adafruit_bme680


BME688_DATA = utils.SENSOR_DATA['bme688']

class BME688(BaseSensor):
    """Represent a BME688 sensor"""
    sensor_type = BME688_DATA.name
    reading_info = BME688_DATA.data

    def __init__(self, *, name=None, **kwargs):
        """Initialize the sensor."""
        super().__init__(name=name, **kwargs)
        i2c = board.I2C()
        self.sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)

    def read_sensor_data(self):
        """Return sensor data as a dict."""
        reading = dict(
            temperature = self.sensor.temperature,  # °C
            humidity = self.sensor.relative_humidity,  # %
            pressure = self.sensor.pressure,  # hPa
            altitude = self.sensor.altitude,  # m
            gas_resistance = self.sensor.gas,  # Ohms
        )
        self.print_reading(reading)
        return reading

if __name__ == '__main__':
    utils.start_sensor(BME688)
