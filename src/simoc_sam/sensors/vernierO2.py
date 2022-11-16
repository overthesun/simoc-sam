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
        self.device.select_sensors([1,2,3])  # o2, temp-corrected o2, temp
        self.device.start()

    def read_sensor_data(self):
        """Return sensor data (O2, temperature) as a dict."""
        measurements = self.device.read()
        o2_percent = measurements[0]
        # o2_temp_corrected = measurements[1]  # For rapid temp fluctations
        temp = measurements[2]
        self.last_reading = dict(o2=o2_percent, temp=temp)
        if self.verbose:
            print(f'O2: {o2_percent:2.2f}%; Temperature: ',
                  f'{temp:2.1f}°C; [{self.sensor_type}]')
        return dict(o2=o2_percent, temp=temp)

if __name__ == '__main__':
    raise ValueError('Vernier sensors cannot be launched independently.')
    # start_sensor(VernierO2)
