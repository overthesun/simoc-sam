import json
import time
import socket

from PIL import Image, ImageDraw, ImageFont

from ..sensors import utils
from .. import config

board = utils.import_board()
import digitalio
import adafruit_ssd1306


WIDTH, HEIGHT = 128, 64
oled_reset = digitalio.DigitalInOut(board.D4)
oled = adafruit_ssd1306.SSD1306_I2C(
    WIDTH, HEIGHT, board.I2C(), addr=0x3D, reset=oled_reset
)

# Fonts
font_small = ImageFont.load_default()
font_header = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14
)

# Record system start time for uptime
START_TIME = time.monotonic()

def read_latest_entry(filepath):
    try:
        with open(filepath) as f:
            for line in f:
                pass
            if line.strip():
                return json.loads(line)
    except Exception as err:
        print(err)
    return {}

def format_values(data_scd, data_bme, data_bno):
    co2 = data_scd.get("co2", "--")
    temp = data_scd.get("temperature", "--")
    hum = data_scd.get("humidity", "--")
    pres = data_bme.get("pressure", "--")
    accx = data_bno.get("accel_x", "--")
    accy = data_bno.get("accel_y", "--")
    accz = data_bno.get("accel_z", "--")
    return [
        "CO2: " + f"{co2:.0f}" if isinstance(co2, float) else str(co2),
        "Tmp: " + f"{temp:.1f}" if isinstance(temp, float) else str(temp),
        "Hum: " + f"{hum:.1f}" if isinstance(hum, float) else str(hum),
        "Prs: " + f"{pres:.1f}" if isinstance(pres, float) else str(pres),
        "A-x: " + f"{accx:.2f}" if isinstance(accx, float) else str(accx),
        "A-y: " + f"{accy:.2f}" if isinstance(accy, float) else str(accy),
        "A-z: " + f"{accz:.2f}" if isinstance(accz, float) else str(accz),
    ]

def format_uptime():
    t = int(time.monotonic())
    hm, s = divmod(t, 60)
    h, m = divmod(hm, 60)
    return f"Rt: {h:02}:{m:02}:{s:02}"

def draw_page(oled, values):
    image = Image.new("1", (oled.height, oled.width))
    draw = ImageDraw.Draw(image)

    # --- Header ---
    draw.text((0, 0), "SIMOC Live", font=font_small, fill=255)
    draw.text((0, 16), format_uptime(), font=font_small, fill=255)

    # --- Sensor Data ---
    y = 34  # leave blank line after uptime
    line_spacing = 14
    for value in values:
        draw.text((0, y), value, font=font_small, fill=255)
        y += line_spacing

    # Rotate for OLED orientation
    image = image.rotate(90, expand=1)
    oled.image(image)
    oled.show()


def main():
    oled.fill(0)
    oled.show()

    log_dir = config.log_dir
    prefix = f'{config.location}_{socket.gethostname()}_'
    while True:
        scd_data = read_latest_entry(log_dir / f'{prefix}SCD-30.jsonl')
        bme_data = read_latest_entry(log_dir / f'{prefix}BME688.jsonl')
        bno_data = read_latest_entry(log_dir / f'{prefix}BNO085.jsonl')

        values = format_values(scd_data, bme_data, bno_data)
        draw_page(oled, values)

if __name__ == "__main__":
    main()

