"""Driver for the BME688 Temp/Humidity/Pressure/Gas Resistance sensor."""
from . import utils
from .basesensor import BaseSensor

board = utils.import_board()
import adafruit_bme680


class BME688(BaseSensor):
    """Represent a BME688 sensor"""
    sensor_type = 'BME688'
    reading_info = {
        'temp': dict(label='Temperature', unit='°C'),
        'rel_hum': dict(label='Relative Humidity', unit='%'),
        'gas_resistance' : dict(label='Gas Resistance', unit='Ohms'),
        'altitude': dict (label='Altitude', unit='m'),
        'pressure': dict(label='Pressure', unit='hPa'),
    }
    def __init__(self, *, name='BME688', **kwargs):
        """Initialize the sensor."""
        super().__init__(name=name, **kwargs)
        i2c = board.I2C()
        self.sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)

    def read_sensor_data(self):
        """Return sensor data as a dict."""
        temperature = self.sensor.temperature  # °C
        humidity = self.sensor.relative_humidity  # %
        pressure = self.sensor.pressure  # hPa
        altitude = self.sensor.altitude  # m
        gas = self.sensor.gas  # Ohms
        if self.verbose:
            print(f'[{self.sensor_type}] Pressure: {pressure:4.1f} hPa; '
                  f'Temperature: {temperature:2.1f}°C; '
                  f'Humidity: {humidity:2.1f}%; Altidude: {altitude:2.1f} m; '
                  f'Gas Resistance: {gas:2.1f} Ohms')
        return {"temp": temperature, "rel_hum": humidity, "gas_resistance": gas,
                "altitude": altitude, "pressure": pressure}

if __name__ == '__main__':
    utils.start_sensor(BME688)
