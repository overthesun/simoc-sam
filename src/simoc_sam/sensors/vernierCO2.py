from .basesensor import BaseSensor
from .vernier_utils import gdx_lite

class VernierCO2(BaseSensor):
    sensor_type = 'Vernier-CO2-Gas'
    reading_info = {
        'co2': dict(label='CO2', unit='ppm'),
        'temp': dict(label='Temperature', unit='°C'),
        'rel_hum': dict(label='Relative Humidity', unit='%'),
    }

    def __init__(self, *, device=None, name='Vernier CO2 Gas', **kwargs):
        """Initialize the sensor."""
        if device is None:
            raise ValueError('Missing device. Try running with vernier.py')
        super().__init__(name=name, **kwargs)
        self.device = gdx_lite(device)
        self.device.select_sensors([1, 2, 3])
        self.device.start()

    def read_sensor_data(self):
        """Return sensor data (CO2, temperature, humidity) as a dict."""
        measurements = self.device.read()
        co2_ppm, temp, rel_hum = measurements
        if self.verbose:
            print(f'CO2: {co2_ppm:4.0f}ppm; Temperature: ',
                  f'{temp:2.1f}°C; Humidity: {rel_hum:2.1f}%; [{self.sensor_type}]')
        return dict(co2=co2_ppm, temp=temp, rel_hum=rel_hum)

if __name__ == '__main__':
    sys.exit('Vernier sensors cannot be launched independently.')
    # start_sensor(VernierCO2)
