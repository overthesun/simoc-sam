# Implement the driver for the SCD-30 CO2/temperature/humidity sensor,
# connected through an MCP2221.

import os
import sys
import asyncio

# set these before import board
os.environ['BLINKA_MCP2221'] = '1'  # we are using MCP2221
os.environ['BLINKA_MCP2221_RESET_DELAY'] = '-1'  # avoid resetting the sensor

try:
    import busio
except RuntimeError:
    sys.exit("Failed to import 'busio', is the sensor plugged in?")

import board  # For MCP-2221
import adafruit_scd30

from basesensor import BaseSensor, SIOWrapper


class SCD30(BaseSensor):
    """Represent a SCD-30 sensors connected through a MCP2221."""
    def __init__(self):
        """Initialize the sensor."""
        super().__init__()
        i2c = busio.I2C(board.SCL, board.SDA, frequency=50000)
        self.scd = adafruit_scd30.SCD30(i2c)

    def read_sensor_data(self):
        """Return sensor data (CO2, temperature, humidity) as a dict."""
        co2_ppm = self.scd.CO2
        temperature = self.scd.temperature  # in °C
        rel_humidity = self.scd.relative_humidity
        return dict(co2=co2_ppm, temp=temperature, rel_hum=rel_humidity)


if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else 8000
    with SCD30() as sensor:
        siowrapper = SIOWrapper(sensor, verbose=True)
        asyncio.run(siowrapper.start(port))
