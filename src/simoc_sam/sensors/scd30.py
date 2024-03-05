"""Driver for the SCD-30 CO2/temperature/humidity sensor."""
from . import utils
from .basesensor import BaseSensor

board = utils.import_board()
busio = utils.import_busio()
import adafruit_scd30



class SCD30(BaseSensor):
    """Represent a SCD-30 sensor."""
    sensor_type = 'SCD-30'
    reading_info = {
        'co2': dict(label='CO2', unit='ppm'),
        'temp': dict(label='Temperature', unit='°C'),
        'rel_hum': dict(label='Relative Humidity', unit='%'),
    }
    def __init__(self, *, name='SCD-30', description=None, verbose=False):
        """Initialize the sensor."""
        super().__init__(name=name, description=description, verbose=verbose)
        i2c = busio.I2C(board.SCL, board.SDA, frequency=50000)
        self.scd = adafruit_scd30.SCD30(i2c)

    def read_sensor_data(self):
        """Return sensor data (CO2, temperature, humidity) as a dict."""
        co2_ppm = self.scd.CO2
        temp = self.scd.temperature  # in °C
        rel_hum = self.scd.relative_humidity
        if self.verbose:
            print(f'[{self.sensor_type}] CO2: {co2_ppm:4.0f}ppm; '
                  f'Temperature: {temp:2.1f}°C; Humidity: {rel_hum:2.1f}%')
        return dict(co2=co2_ppm, temp=temp, rel_hum=rel_hum)


if __name__ == '__main__':
    utils.start_sensor(SCD30)
