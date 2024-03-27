import random

from . import utils
from .basesensor import BaseSensor


MOCK_DATA = utils.SENSOR_DATA['Mock']

class MockSensor(BaseSensor):
    """A mock sensor that generates random CO2/temperature/humidity data."""
    sensor_type = MOCK_DATA.name
    reading_info = MOCK_DATA.data

    def __init__(self, *, name=None, description=None, verbose=False,
                 base_co2=500, base_temp=20, base_hum=50,
                 base_altitude=1000, base_pressure=900):
        super().__init__(name=name, description=description, verbose=verbose)
        self.co2_ppm = base_co2
        self.temp = base_temp
        self.rel_hum = base_hum
        self.altitude = base_altitude
        self.pressure = base_pressure

    def read_sensor_data(self):
        # add/remove random values to/from the previous ones
        self.co2_ppm += random.randint(1, 50) * random.choice([-1, 0, +1])
        self.temp += random.random() * random.choice([-1, 0, +1])
        self.rel_hum += random.randint(1, 3) * random.choice([-1, 0, +1])
        self.altitude += random.random() * random.choice([-1, 0, +1])
        self.pressure += random.randint(1, 5) * random.choice([-1, 0, +1])
        # clip values to be within range
        self.co2_ppm = float(max(0, min(self.co2_ppm, 5000)))
        self.temp = float(max(15, min(self.temp, 25)))
        self.rel_hum = float(max(0, min(self.rel_hum, 100)))
        self.altitude = float(max(0, min(self.altitude, 10000)))
        self.pressure = float(max(0, min(self.pressure, 10000)))
        reading = dict(
            co2=self.co2_ppm,
            temperature=self.temp,
            humidity=self.rel_hum,
            altitude=self.altitude,
            pressure=self.pressure,
        )
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(MockSensor)
