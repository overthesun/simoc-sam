"""Driver for the SGP30 TVOC/eCO2 Gas sensor."""
import math

from . import utils
from .basesensor import BaseSensor

board = utils.import_board()
busio = utils.import_busio()
import adafruit_sgp30


# These equations are provided by the Sensirion datasheet for the SGP-30.
# 20997 and 14296 are experimental values in a room assumed to have "typical"
# concentration of 14.85 ppm, although this is an unmeasured assumption.
def tick_conversion_ethanol(signal_output):
    """Get raw ticks from sensor and converts to ppm."""
    signal_reference = 20997
    return 0.4 * (math.e**((signal_reference-signal_output)/512))

def tick_conversion_H2(signal_output):
    """Get raw ticks from sensor and converts to ppm."""on.
    signal_reference = 14296
    return 0.5 * (math.e**((signal_reference-signal_output)/512))


SGP30_DATA = utils.SENSOR_DATA['SGP-30']

class SGP30(BaseSensor):
    """Represent a SGP30 sensor."""
    sensor_type = SGP30_DATA.name
    reading_info = SGP30_DATA.data

    def __init__(self, *, name=None, verbose=False):
        """Initialize the sensor."""
        super().__init__(name=name, verbose=verbose)
        i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
        self.sensor = adafruit_sgp30.Adafruit_SGP30(i2c)
        self.sensor.iaq_init()
        self.sensor.set_iaq_baseline(0x8973, 0x8AEE)  # Numbers from adafruit example

    def read_sensor_data(self):
        """Return sensor data (H2, Ethanol, eCO2, TVOC) as a dict."""
        hydrogen_ticks = self.sensor.H2  # raw hydrogen ticks
        ethanol_ticks = self.sensor.Ethanol  # raw ethanol ticks
        reading = dict(
            H2=tick_conversion_H2(hydrogen_ticks),  # convert to ppm
            ethanol=tick_conversion_ethanol(ethanol_ticks),  # convert to ppm
            # get estimated CO2 and VOC values interpreted from H2 an Ethanol
            eCO2=self.sensor.eCO2,  # ppm
            TVOC=self.sensor.TVOC,  # ppb
        )
        self.print_reading(reading)
        return reading

if __name__ == '__main__':
    utils.start_sensor(SGP30)
