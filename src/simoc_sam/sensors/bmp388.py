"""Driver for the BMP388 Temperature, Barometric Pressure and Altitude sensor."""
from . import utils
from .basesensor import BaseSensor

board = utils.import_board()
import adafruit_bmp3xx


class BMP388(BaseSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        i2c = board.I2C()
        self.sensor = adafruit_bmp3xx.BMP3XX_I2C(i2c)
        # Set oversampling for better accuracy
        self.sensor.pressure_oversampling = 8
        self.sensor.temperature_oversampling = 2

    def read_sensor_data(self):
        """Return sensor data as a dict."""
        reading = dict(
            temperature = self.sensor.temperature,  # °C (±0.5°C)
            pressure = self.sensor.pressure,  # hPa
            altitude = self.sensor.altitude,  # m (±0.5 m)
        )
        self.print_reading(reading)
        return reading

if __name__ == '__main__':
    utils.start_sensor(BMP388)
