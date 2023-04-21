import sys

from .basesensor import BaseSensor
from .vernier_utils import gdx_lite

class VernierO2(BaseSensor):
    sensor_type = 'Vernier-O2-Gas'
    reading_info = {
        'o2': dict(label='O2', unit='%'),
        'temp': dict(label='Temperature', unit='°C'),
    }

    def __init__(self, *, device=None, name='Vernier O2 Gas', **kwargs):
        """Initialize the sensor."""
        if device is None:
            raise ValueError('Missing device. Try running with vernier.py')
        super().__init__(name=name, **kwargs)
        self.device = gdx_lite(device)
        self.device.select_sensors([1, 2, 3])  # o2, temp-corrected o2, temp
        self.device.start()

    def __exit__(self, type, value, traceback):
        self.device.close()

    def read_sensor_data(self):
        """Return sensor data (O2, temperature) as a dict."""
        measurements = self.device.read()
        o2_percent = measurements[0]
        # o2_temp_corrected = measurements[1]  # For rapid temp fluctations
        temp = measurements[2]
        if self.verbose:
            print(f'[{self.sensor_type}] '
                  f'O2: {o2_percent:2.2f}%; Temperature: {temp:2.1f}°C')
        return dict(o2=o2_percent, temp=temp)

if __name__ == '__main__':
    sys.exit('Vernier sensors cannot be launched independently.')
    # start_sensor(VernierO2)
