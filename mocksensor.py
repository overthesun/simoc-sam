import sys
import random
import asyncio

from basesensor import BaseSensor, SIOWrapper


class MockSensor(BaseSensor):
    """A mock server that generates random CO2/temperature/humidity data."""
    def __init__(self, *, base_co2=500, base_temp=20, base_hum=50, verbose=False):
        super().__init__(verbose=verbose)
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
        if self.verbose:
            print(f'CO2: {self.co2_ppm:4.0f}ppm; Temperature: '
                  f'{self.temp:2.1f}°C; Humidity: {self.rel_hum:2.1f}%')
        return dict(co2=self.co2_ppm, temp=self.temp, rel_hum=self.rel_hum)


if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else 8000
    with MockSensor(verbose=True) as sensor:
        siowrapper = SIOWrapper(sensor, verbose=True)
        asyncio.run(siowrapper.start(port))
