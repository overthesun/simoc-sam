import random

from . import utils
from .basesensor import BaseSensor


MOCK_DATA = utils.SENSOR_DATA['Mock']

class MockSensor(BaseSensor):
    """A mock sensor that generates random CO2/temperature/humidity data."""
    sensor_type = MOCK_DATA.name
    reading_info = MOCK_DATA.data

    def __init__(self, *, base_co2=500, base_temp=20, base_hum=50,
                 name=None, description=None, verbose=False):
        super().__init__(name=name, description=description, verbose=verbose)
        self.co2_ppm = base_co2
        self.temp = base_temp
        self.rel_hum = base_hum

    def read_sensor_data(self):
        # add/remove random values to/from the previous ones
        self.co2_ppm += random.randint(1, 50) * random.choice([-1, 0, +1])
        self.temp += random.random() * random.choice([-1, 0, +1])
        self.rel_hum += random.randint(1, 3) * random.choice([-1, 0, +1])
        # clip values to be within range
        self.co2_ppm = float(max(0, min(self.co2_ppm, 5000)))
        self.temp = float(max(15, min(self.temp, 25)))
        self.rel_hum = float(max(0, min(self.rel_hum, 100)))
        reading = dict(
            co2=self.co2_ppm,
            temperature=self.temp,
            humidity=self.rel_hum,
        )
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(MockSensor)
