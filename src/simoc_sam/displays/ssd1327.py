"""Driver for the Adafruit SSD1327 OLED display (128x128 Grayscale)."""

import time
import asyncio

import displayio
import adafruit_ssd1327

from i2cdisplaybus import I2CDisplayBus

from simoc_sam import utils, config
from simoc_sam.displays import utils as display_utils


# store latest readings from each sensor (updated by MQTT handler)
SENSOR_READINGS = {}

# number of rows for 128x128 display (including header)
MAX_ROWS = 15


def blit_image_to_bitmap(bitmap, image, width):
    """Write a 1-bit PIL image into the existing bitmap in-place.

    Only writes pixels that differ from the bitmap's current state.
    Returns the number of pixels changed.
    """
    pixels = image.getdata()
    changes = 0
    for i, pixel in enumerate(pixels):
        val = 1 if pixel else 0
        x = i % width
        y = i // width
        if bitmap[x, y] != val:
            bitmap[x, y] = val
            changes += 1
    return changes


async def update_display(display, bitmap, width, height):
    """Continuously update the display with latest sensor values."""
    prev_rows = None
    while True:
        t_start = time.time()
        rows = display_utils.format_values(SENSOR_READINGS, max_rows=MAX_ROWS)
        if rows != prev_rows:
            image = display_utils.draw_image(width, height, rows)
            if image:
                blit_image_to_bitmap(bitmap, image, width)
                display.refresh()
            prev_rows = rows
        # subtract full cycle time (writes + I2C refresh) from sleep
        elapsed = time.time() - t_start
        sleep_time = max(0, config.display_refresh - elapsed)
        await asyncio.sleep(sleep_time)


async def main():
    """Main loop: read sensor values and display them on the OLED."""
    display_config = display_utils.DISPLAY_DATA['ssd1327']
    width, height = display_config.width, display_config.height
    # initialize display
    displayio.release_displays()
    display_bus = I2CDisplayBus(
        utils.get_i2c(),
        device_address=display_config.i2c_address,
    )
    display = adafruit_ssd1327.SSD1327(display_bus, width=width, height=height)
    # create a 2-color bitmap and a tile grid to hold it
    bitmap = displayio.Bitmap(width, height, 2)
    palette = displayio.Palette(2)
    palette[0] = 0x000000  # black
    palette[1] = 0xFFFFFF  # white
    tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
    group = displayio.Group()
    group.append(tile_grid)
    display.root_group = group
    display.auto_refresh = False
    # start MQTT monitor and display update tasks
    await asyncio.gather(
        display_utils.mqtt_monitor(SENSOR_READINGS),
        update_display(display, bitmap, width, height),
    )


if __name__ == "__main__":
    asyncio.run(main())
