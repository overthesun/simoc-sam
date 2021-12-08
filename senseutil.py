# This script is used to gather data from the SCD-30 sensor attached to
# the MCP-2221. This is a minimal script with most features stripped out so that
# developers can more easily troubleshoot issues with running it containerized.

# Normal Packages
import os
import sys
os.environ['BLINKA_MCP2221'] = '1'
import time

# Special packages
try:
    import busio
except RuntimeError:
    print("Script failed during busio import. "
          "Probably the sensor is not plugged in.")
    sys.exit()
import adafruit_scd30
import board  # For MCP-2221

class Sensor:
    def __init__(self):
        self.scd=initialize_sensor()

def initialize_sensor():
    """Initialize the sensor."""

    i2c = busio.I2C(board.SCL, board.SDA, frequency=50000)
    scd = adafruit_scd30.SCD30(i2c)
    return scd

def get_interval_data(scd, time_elapsed):
    ''' This function gets the data from the sensor directly and packages it
         with the time that the sensor data was retrieved from the sensor. '''
    cO2_ppm = scd.CO2
    temperature = scd.temperature  # in *C
    rel_humidity = scd.relative_humidity
    interval_data = dict(seconds=time_elapsed, co2=cO2_ppm,
                         temp=temperature, humidity=rel_humidity)
    return interval_data


# This method is only if this script is called on its own.
def sensor_loop():
    start_time = time.time()
    while True:
        current_time = time.time()
        time_elapsed = current_time - start_time
        # Check for new data, available every 2 seconds
        try:
            if scd.data_available:  # If fresh data is available, get it
                error_count = 0
                interval_data = get_interval_data(scd, time_elapsed)
                print(interval_data)
        except RuntimeError as e:
            # Occasionally sensor does not want to respond but skipping it is
            # usually OKAY.
            print(e)  # Print the error
        # Without this line, your system fans will kick up and not be happy.
        time.sleep(scd.measurement_interval/4)

# If called directly, start sensor loop
if __name__ == '__main__':
    # Start the sensor script here
    scd = initialize_sensor()
    sensor_loop()
