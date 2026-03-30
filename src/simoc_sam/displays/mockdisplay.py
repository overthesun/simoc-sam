"""Mock display driver that prints sensor data to the console."""

import asyncio

from rich.live import Live
from rich.text import Text

from simoc_sam import config
from simoc_sam.displays import utils as display_utils

# store latest readings from each sensor (updated by MQTT handler)
SENSOR_READINGS = {}

# total rows to display (including header)
MAX_ROWS = 50

async def update_display():
    """Continuously update the console display with latest sensor values."""
    delimiter = "-" * 40
    with Live(refresh_per_second=1 / (config.display_refresh or 1)) as live:
        try:
            while True:
                rows = display_utils.format_values(SENSOR_READINGS, max_rows=MAX_ROWS)
                output = Text("\n".join([delimiter, *rows, delimiter]))
                live.update(output)
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
