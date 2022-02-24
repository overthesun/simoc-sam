# This script enables running more than one sensor.

import os
import threading
import utils

from utils import start_sensor
from bme688 import BME688
from sgp30 import SGP30
from scd30 import SCD30

if utils.check_for_MCP2221():
    # We don't want to import board again if MCP2221 is already running from
    # another script 
    if 'BLINKA_MCP2221' not in os.environ:
        # set these before import board
        os.environ['BLINKA_MCP2221'] = '1'  # we are using MCP2221
        os.environ['BLINKA_MCP2221_RESET_DELAY'] = '-1'  # avoid resetting the sensor
    import board
    import bme688
    import scd30
    import sgp30
    bme = threading.Thread(target=utils.start_sensor, args=(BME688,))
    bme.start()
    sgp = threading.Thread(target=utils.start_sensor, args=(SGP30,))
    sgp.start()
    scd = threading.Thread(target=utils.start_sensor, args=(SCD30,))
    scd.start()

else:
    print("No MCP-2221 Detected")
