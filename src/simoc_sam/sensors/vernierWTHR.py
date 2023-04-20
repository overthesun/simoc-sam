import sys

from .basesensor import BaseSensor
from .vernier_utils import gdx_lite

class VernierWTHR(BaseSensor):
    sensor_type = 'Vernier-WTHR'
    reading_info = {
        'wind_speed': dict(label='Wind Speed', unit='m/s'),
        'wind_direction': dict(label='Wind Direction', unit='°'),
        'wind_chill': dict(label='Wind Chill', unit='°C'),
        'temp': dict(label='Temperature', unit='°C'),
        'heat_index': dict(label='Heat Index', unit='°C'),
        'dew_point': dict(label='Dew Point', unit='°C'),
        'rel_hum': dict(label='Relative Humidity', unit='%'),
        'absolute_humidity': dict(label='Absolute Humidity', unit='g/m^3'),
        'station_pressure': dict(label='Station Pressure', unit='mbar'),
        'pressure': dict(label='Barometric Pressure', unit='mbar'),
        'altitude': dict(label='Altitude', unit='m'),
    }

    def __init__(self, *, device=None, name='Vernier Weather', **kwargs):
        """Initialize the sensor."""
        if device is None:
            raise ValueError('Missing device. Try running with vernier.py')
        super().__init__(name=name, **kwargs)
        self.device = gdx_lite(device)
        self.device.select_sensors([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
        self.device.start()

    def __exit__(self, type, value, traceback):
        self.device.close()

    def read_sensor_data(self):
        """Return all sensor data as a dict."""
        measurements = self.device.read()

        wind_speed = measurements[0]  # m/s
        wind_direction = measurements[1]  # °
        wind_chill = measurements[2]  # °C
        temp = measurements[3]  # °C
        heat_index = measurements[4]  # °C
        dew_point = measurements[5]  # °C
        rel_hum = measurements[6]  # %
        absolute_humidity = measurements[7]  # g/m^3
        station_pressure = measurements[8]  # mbar
        pressure = measurements[9]  # mbar
        altitude = measurements[10]  # m

        if self.verbose:
            print(f'Wind Speed: {wind_speed:2.1f}m/s; '
                  f'Wind Direction: {wind_direction:2.1f}°; '
                  f'Wind Chill: {wind_chill:2.1f}°C; '
                  f'Temperature: {temp:2.1f}°C; '
                  f'Heat Index: {heat_index:2.1f}°C; '
                  f'Dew Point: {dew_point:2.1f}°C; '
                  f'Relative Humidity: {rel_hum:2.1f}%; '
                  f'Absolute Humidity: {absolute_humidity:2.1f}g/m^3; '
                  f'Station Pressure: {station_pressure:2.1f}mbar; '
                  f'Barometric Pressure: {pressure:2.1f}mbar; '
                  f'Altitude: {altitude:2.1f}m; [{self.sensor_type}]')
        return dict(
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            wind_chill=wind_chill,
            temp=temp,
            heat_index=heat_index,
            dew_point=dew_point,
            rel_hum=rel_hum,
            absolute_humidity=absolute_humidity,
            station_pressure=station_pressure,
            pressure=pressure,
            altitude=altitude,
        )

if __name__ == '__main__':
    sys.exit('Vernier sensors cannot be launched independently.')
    # start_sensor(VernierWTHR)
