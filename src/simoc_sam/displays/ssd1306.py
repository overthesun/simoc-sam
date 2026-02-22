"""Driver for the Adafruit SSD1306 OLED displays (128x64 and 128x32)."""

import sys
import asyncio

from simoc_sam.sensors import utils as sensor_utils
board = sensor_utils.import_board()

import digitalio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont

from simoc_sam import utils
from simoc_sam.displays import utils as display_utils


# store latest readings from each sensor (updated by MQTT handler)
SENSOR_READINGS = {}

# number of rows to display for sensor values (after header rows)
MAX_ROWS = 9


def draw_page(oled, sensor_values):
    """Draw sensor values on the OLED display."""
    image = Image.new("1", (oled.height, oled.width))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    # header
    draw.text((0, 0), "SIMOC LIVE", font=font, fill=255)
    draw.text((0, 12), utils.uptime(), font=font, fill=255)
    # sensor values
    if sensor_values:
        header_height = 30
        usable_height = oled.width - header_height  # screen is rotated
        num_rows = len(sensor_values)
        spacing = max(8, usable_height // num_rows)
        y = header_height
        for row in sensor_values:
            draw.text((0, y), row, font=font, fill=255)
            y += spacing
    oled.image(image.rotate(90, expand=True))
    oled.show()


async def update_display(oled):
    """Continuously update the display with latest sensor values."""
    try:
        while True:
            sensor_values = display_utils.format_values(SENSOR_READINGS, max_rows=MAX_ROWS)
            draw_page(oled, sensor_values)
            await asyncio.sleep(1)  # refresh display once per second
    except asyncio.CancelledError:
        # clear display on shutdown
        oled.fill(0)
        oled.show()
        raise


async def main(display_key=None):
    """Main loop: read sensor values and display them on the OLED."""
    # determine which display to use
    if display_key is None:
        if len(sys.argv) > 1:
            display_key = sys.argv[1]
        else:
            display_key = 'ssd1306_128x64'  # default
    # load display config
    if display_key not in display_utils.DISPLAY_DATA:
        print(f"Error: Unknown display '{display_key}'")
        print(f"Available displays: {list(display_utils.DISPLAY_DATA.keys())}")
        sys.exit(1)
    display_config = display_utils.DISPLAY_DATA[display_key]
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
    display_key = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(display_key))
