"""Driver for the BMP388 Temperature, Barometric Pressure, and Altitude sensor."""
from . import utils
from .basesensor import AdafruitSensor


class BMP388(AdafruitSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from adafruit_bmp3xx import BMP3XX_I2C
        i2c = self.board.I2C()
        self.sensor = BMP3XX_I2C(i2c)
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
