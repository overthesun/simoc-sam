"""Driver for the BME688 Temp/Humidity/Pressure/Gas Resistance sensor."""
from . import utils
from .basesensor import BaseSensor


class BME688(BaseSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from adafruit_bme680 import Adafruit_BME680_I2C
        i2c = self.board.I2C()
        self.sensor = Adafruit_BME680_I2C(i2c, debug=False)

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
