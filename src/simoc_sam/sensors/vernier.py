from godirect import GoDirect

from .vernierCO2 import VernierCO2
from .vernierO2 import VernierO2
from .vernier_utils import start_sensors

def init_sensors():
    """Initialize multiple Vernier sensors from the same host."""
    gd = GoDirect(use_ble=False, use_usb=True)
    devices = gd.list_devices()
    sensor_classes = []
    for device in devices:
        device.open()
        name = device._name
        serial_number = device._serial_number
        if name.startswith('GDX-CO2'):
            print(f'Found CO2 sensor {serial_number}; starting device...')
            sensor_classes.append((VernierCO2, device, dict(id=serial_number)))
        elif name.startswith('GDX-O2'):
            print(f'Found O2 sensor {serial_number}; starting deivce...')
            sensor_classes.append((VernierO2, device, dict(id=serial_number)))
        else:
            print(f'Found unrecognized device: {name}')
            break
    print(sensor_classes)
    start_sensors(sensor_classes)


if __name__ == '__main__':
    init_sensors()
