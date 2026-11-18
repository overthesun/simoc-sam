"""Driver for the PMSA003I particulate matter sensor."""
from . import utils
from .basesensor import AdafruitSensor


class PMSA003I(AdafruitSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from adafruit_pm25.i2c import PM25_I2C
        self.sensor = PM25_I2C(self.board.I2C())

    def read_sensor_data(self):
        """Return particulate concentrations and particle counts."""
        data = self.sensor.read()
        reading = {
            'pm10_standard': data['pm10 standard'],
            'pm25_standard': data['pm25 standard'],
            'pm100_standard': data['pm100 standard'],
            'pm10_environmental': data['pm10 env'],
            'pm25_environmental': data['pm25 env'],
            'pm100_environmental': data['pm100 env'],
            'particles_0_3um': data['particles 03um'],
            'particles_0_5um': data['particles 05um'],
            'particles_1_0um': data['particles 10um'],
            'particles_2_5um': data['particles 25um'],
            'particles_5_0um': data['particles 50um'],
            'particles_10um': data['particles 100um'],
        }
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(PMSA003I)
