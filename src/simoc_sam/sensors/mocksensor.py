import random

from . import utils
from .basesensor import BaseSensor


MOCK_DATA = utils.SENSOR_DATA['Mock']

class MockSensor(BaseSensor):
    """A mock sensor that generates random CO2/temperature/humidity data."""
    sensor_type = MOCK_DATA.name
    reading_info = MOCK_DATA.data

    def __init__(self, *, name=None, description=None, verbose=False,
                 base_co2=1000, base_temp=20, base_hum=50,
                 base_altitude=1000, base_pressure=900):
        super().__init__(name=name, description=description, verbose=verbose)
        self.co2_ppm = self.gen_values(base_co2, offset=50, range=(0, 5000))
        self.temp = self.gen_values(base_temp, offset=1, range=(0, 40))
        self.rel_hum = self.gen_values(base_hum, offset=3, range=(0, 100))
        self.altitude = self.gen_values(base_altitude, offset=1, range=(0, 10000))
        self.pressure = self.gen_values(base_pressure, offset=5, range=(0, 10000))

    def gen_values(self, value, offset, range):
        """Generate random values starting from values +-offset, within range."""
        range_min, range_max = range  # value must be within this range
        while True:
            value = random.gauss(value, offset/3)
            value = float(max(range_min, min(value, range_max)))
            yield value

    def read_sensor_data(self):
        reading = dict(
            co2=next(self.co2_ppm),
            temperature=next(self.temp),
            humidity=next(self.rel_hum),
            altitude=next(self.altitude),
            pressure=next(self.pressure),
        )
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(MockSensor)
