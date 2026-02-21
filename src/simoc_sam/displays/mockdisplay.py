"""Mock display driver that prints sensor data to the console."""

import asyncio

from simoc_sam.utils import uptime
from simoc_sam.displays import utils as display_utils

# store latest readings from each sensor (updated by MQTT handler)
SENSOR_READINGS = {}

def display_values(sensor_values):
    """Print sensor values to console."""
    print("=" * 40)
    print("SIMOC LIVE")
    print(uptime())
    print("-" * 40)
    for value in sensor_values:
        print(value)
    print("=" * 40)

async def update_display():
    """Continuously update the console display with latest sensor values."""
    try:
        while True:
            sensor_values = display_utils.format_values(SENSOR_READINGS)
            display_values(sensor_values)
            await asyncio.sleep(1)  # refresh display once per second
    except asyncio.CancelledError:
        print("\nMockDisplay stopped.")
        raise

async def main():
    """Main loop: monitor MQTT and display sensor values."""
    print("MockDisplay started. Press Ctrl+C to exit.")
    # start MQTT monitor and display update tasks
    await asyncio.gather(
        asyncio.create_task(display_utils.mqtt_monitor(SENSOR_READINGS)),
        asyncio.create_task(update_display()),
        return_exceptions=True,
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMockDisplay stopped.")
