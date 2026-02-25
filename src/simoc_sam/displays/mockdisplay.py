"""Mock display driver that prints sensor data to the console."""

import asyncio

from simoc_sam import config
from simoc_sam.displays import utils as display_utils

# store latest readings from each sensor (updated by MQTT handler)
SENSOR_READINGS = {}

# Total rows to display (including header)
MAX_ROWS = 9

def display_values(rows):
    """Print display rows to console."""
    print("-" * 40)
    for row in rows:
        print(row)
    print("-" * 40)

async def update_display():
    """Continuously update the console display with latest sensor values."""
    try:
        while True:
            rows = display_utils.format_values(SENSOR_READINGS, max_rows=MAX_ROWS)
            display_values(rows)
            await asyncio.sleep(config.display_refresh)
    except asyncio.CancelledError:
        print("\nMockDisplay stopped.")
        raise

async def main():
    """Main loop: monitor MQTT and display sensor values."""
    print("MockDisplay started. Press Ctrl+C to exit.")
    # start MQTT monitor and display update tasks
    await asyncio.gather(
        display_utils.mqtt_monitor(SENSOR_READINGS),
        update_display(),
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMockDisplay stopped.")
