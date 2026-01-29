"""Driver for the Adafruit SSD1306 OLED displays (128x64 and 128x32)."""

import sys
import asyncio

import board
import digitalio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont

from simoc_sam.sensors.basesensor import get_log_path
from simoc_sam.displays import utils as display_utils
from simoc_sam import utils


MAX_ROWS = 9

SENSOR_FILES = {
    'scd30': get_log_path('scd30'),
    'sgp30': get_log_path('sgp30'),
    'bme688': get_log_path('bme688'),
    'tsl2591': get_log_path('tsl2591'),
    'bno085': get_log_path('bno085'),
}

DISPLAY_ORDER = ['scd30', 'sgp30', 'bme688', 'tsl2591', 'bno085']

# store latest readings from each sensor
SENSOR_READINGS = {}


def get_sensor_values():
    """Format latest sensor values for display."""
    rows = []

    for sensor in DISPLAY_ORDER:
        data = SENSOR_READINGS.get(sensor)
        if not data:
            continue

        if sensor == 'scd30':
            rows.append(f"CO2: {data.get('co2', 0):.0f}")
            rows.append(f"T: {data.get('temperature', 0):.2f}C")
            rows.append(f"RH: {data.get('humidity', 0):.2f}%")
        elif sensor == 'sgp30':
            rows.append(f"VOC: {data.get('tvoc', 0)}")
        elif sensor == 'bme688':
            rows.append(f"Pr: {data.get('pressure', 0):.2f}")
        elif sensor == 'tsl2591':
            rows.append(f"Lt: {data.get('light', 0):.2f}")
        elif sensor == 'bno085':
            for axis in ['linear_accel_x', 'linear_accel_y', 'linear_accel_z']:
                val = data.get(axis, 0)
                if isinstance(val, str):
                    val = 0
                rows.append(f"A-{axis[-1]}: {val:.2f}")

        if len(rows) >= MAX_ROWS:
            rows = rows[:MAX_ROWS]
            break

    return rows


def draw_page(oled, font, sensor_values, width):
    """Draw sensor values on the OLED display."""
    image = Image.new("1", (oled.height, oled.width))
    draw = ImageDraw.Draw(image)

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


async def monitor_sensor(sensor):
    """Monitor a sensor log file and update SENSOR_READINGS."""
    filepath = SENSOR_FILES.get(sensor)
    if not filepath:
        return
    print(f'Starting to monitor {sensor} log: {filepath}')
    async for reading in utils.read_jsonl_file(filepath):
        SENSOR_READINGS[sensor] = reading


async def update_display(oled, font, width):
    """Continuously update the display with latest sensor values."""
    try:
        while True:
            sensor_values = get_sensor_values()
            draw_page(oled, font, sensor_values, width)
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
    oled_reset = digitalio.DigitalInOut(display_config.reset_pin)
    oled = adafruit_ssd1306.SSD1306_I2C(
        display_config.width,
        display_config.height,
        board.I2C(),
        addr=display_config.i2c_address,
        reset=oled_reset
    )
    font = ImageFont.load_default()

    oled.fill(0)
    oled.show()

    # start monitoring tasks for each sensor
    tasks = []
    for sensor in DISPLAY_ORDER:
        if sensor in SENSOR_FILES:
            tasks.append(asyncio.create_task(monitor_sensor(sensor)))

    # start display update task
    tasks.append(asyncio.create_task(update_display(oled, font, display_config.width)))

    # run all tasks
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    display_key = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(display_key))
