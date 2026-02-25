"""Driver for the Adafruit SSD1306 OLED displays (128x64 and 128x32)."""

import asyncio

from simoc_sam.sensors import utils as sensor_utils
board = sensor_utils.import_board()

import digitalio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont

from simoc_sam import utils, config
from simoc_sam.displays import utils as display_utils


# store latest readings from each sensor (updated by MQTT handler)
SENSOR_READINGS = {}

# number of rows for 128x64 rotated 90 degrees
# With configurable format, this is the total rows including header
MAX_ROWS = 9


def draw_page(oled, rows):
    """Draw sensor values on the OLED display."""
    image = Image.new("1", (oled.height, oled.width))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    if not rows:
        return  # nothing to display
    # screen is rotated, so oled.width is actually the height
    spacing = max(8, oled.width // len(rows))  # calc row height dynamically
    y = 0
    for row in rows:
        if not row.strip():
            y += 6  # add extra spacing for blank lines
        else:
            draw.text((0, y), row, font=font, fill=255)
            y += spacing
    oled.image(image.rotate(90, expand=True))
    oled.show()


async def update_display(oled):
    """Continuously update the display with latest sensor values."""
    try:
        while True:
            rows = display_utils.format_values(SENSOR_READINGS, max_rows=MAX_ROWS)
            draw_page(oled, rows)
            await asyncio.sleep(config.display_refresh)
    except asyncio.CancelledError:
        # clear display on shutdown
        oled.fill(0)
        oled.show()
        raise


async def main():
    """Main loop: read sensor values and display them on the OLED."""
    display_config = display_utils.DISPLAY_DATA['ssd1306']
    # initialize display
    oled_reset = digitalio.DigitalInOut(getattr(board, display_config.reset_pin))
    oled = adafruit_ssd1306.SSD1306_I2C(
        display_config.width,
        display_config.height,
        utils.get_i2c(),
        addr=display_config.i2c_address,
        reset=oled_reset,
    )
    oled.fill(0)
    oled.show()
    # start MQTT monitor and display update tasks
    await asyncio.gather(
        display_utils.mqtt_monitor(SENSOR_READINGS),
        update_display(oled),
        return_exceptions=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
