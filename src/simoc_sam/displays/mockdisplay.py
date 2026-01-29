"""Mock display driver that prints sensor data to the console."""

import random
import time


def gen_value(base, offset, range_min, range_max):
    """Generate random values starting from base +-offset, within range."""
    value = base
    while True:
        value = random.gauss(value, offset/3)
        value = float(max(range_min, min(value, range_max)))
        yield value


def uptime():
    """Return uptime string in HH:MM:SS format."""
    t = int(time.monotonic())
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"Up {h:02}:{m:02}:{s:02}"


def get_sensor_values():
    """Generate random sensor values for display."""
    return [
        f"CO2: {next(co2_gen):.0f}",
        f"T: {next(temp_gen):.2f}C",
        f"RH: {next(hum_gen):.2f}%",
        f"VOC: {int(next(voc_gen))}",
        f"Pr: {next(pressure_gen):.2f}",
        f"Lt: {next(light_gen):.2f}",
        f"A-x: {next(accel_x_gen):.2f}",
        f"A-y: {next(accel_y_gen):.2f}",
        f"A-z: {next(accel_z_gen):.2f}",
    ]


def display_values(sensor_values):
    """Print sensor values to console."""
    print("=" * 40)
    print("SIMOC LIVE")
    print(uptime())
    print("-" * 40)
    for value in sensor_values:
        print(value)
    print("=" * 40)


# initialize generators
co2_gen = gen_value(450, 20, 400, 2000)
temp_gen = gen_value(22, 1, 15, 30)
hum_gen = gen_value(50, 3, 20, 80)
voc_gen = gen_value(100, 20, 0, 500)
pressure_gen = gen_value(1013, 5, 900, 1100)
light_gen = gen_value(300, 50, 0, 1000)
accel_x_gen = gen_value(0, 0.1, -2, 2)
accel_y_gen = gen_value(0, 0.1, -2, 2)
accel_z_gen = gen_value(9.8, 0.1, 8, 11)


def main():
    """Main loop: generate and display sensor values."""
    print("MockDisplay started. Press Ctrl+C to exit.")
    try:
        while True:
            sensor_values = get_sensor_values()
            display_values(sensor_values)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMockDisplay stopped.")


if __name__ == "__main__":
    main()
