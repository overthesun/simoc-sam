import threading

from godirect import GoDirect

from vernier_CO2 import VernierCO2
from vernier_O2 import VernierO2
from utils import start_sensors

def init_sensors():
    gd = GoDirect(use_ble=False, use_usb=True)
    devices = gd.list_devices()
    for device in devices:
        device.open()
        name = device._name
        serial_number = device._serial_number
        sensor_classes = []
        if name.startswith('GDX-CO2'):
            print(f'Found CO2 sensor {serial_number}; starting deivce...')
            # start_sensor(VernierCO2, device=device, serial_number=serial_number)
            sensor_classes.append((VernierCO2, device))
        elif name.startswith('GDX-O2'):
            print(f'Found O2 sensor {serial_number}; starting deivce...')
            # start_sensor(VernierO2, device=device, serial_number=serial_number)
            sensor_classes.append((VernierO2, device))
        else:
            print(f'Found unrecognized device: {name}')
            break
    start_sensors(sensor_classes)

if __name__ == '__main__':
    init_sensors()
