import os
import socket
import subprocess

try:
    import netifaces
except ImportError:
    netifaces = None


# Network info

def print_hostname():
    """Print current hostname."""
    print(f'Hostname: {socket.gethostname()}')

def print_addresses(ifaces_prefixes=('wl', 'bat', 'enp', 'eth')):
    """Print MAC/IPv4/IPv6 addresses for WiFi/BATMAN/ethernet interfaces."""
    interfaces = netifaces.interfaces()
    found_ifaces = {}
    for iface in interfaces:
        if iface.startswith(ifaces_prefixes):
            found_ifaces[iface] = netifaces.ifaddresses(iface)
    if not found_ifaces:
        print(f'No interface with the following prefixes found: {ifaces_prefixes}')
        print(f'Available interfaces: {interfaces}')
        return
    addr_types = {
        'MAC': netifaces.AF_LINK,
        'IPv4': netifaces.AF_INET,
        'IPv6': netifaces.AF_INET6,
    }
    print('IP/MAC addresses:')
    for iface, addresses in found_ifaces.items():
        print(f'* {iface}:')
        for type, const in addr_types.items():
            if const not in addresses:
                continue
            addr = addresses[const][0]['addr']
            print(f'  {type:4}: {addr}')

def print_batman():
    """Print BATMAN info (neighbors/originators tables)."""
    if not [iface for iface in netifaces.interfaces()
            if iface.startswith('bat')]:
        print('BATMAN: no interface detected')
        return
    print('BATMAN mesh:')
    subprocess.run(['sudo', 'batctl', 'n'])
    subprocess.run(['sudo', 'batctl', 'o'])


# Sensors info

def has_mcp():
    return b'MCP2221' in subprocess.check_output("lsusb")

def print_MCP2221_info():
    """Print True if the MCP2221 is connected, False otherwise."""
    print(f'MCP2221 connected: {has_mcp()}')

def print_sensors():
    """Print a list of connected sensors and their I2C addresses."""
    if has_mcp():
        os.environ['BLINKA_MCP2221'] = '1'
        os.environ['BLINKA_MCP2221_RESET_DELAY'] = '-1'
    try:
        import board
    except (ImportError, OSError):
        print('Sensor scanning failed.')
        return  # doesn't always work with RPi + MCP2221
    import busio
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
    except (AttributeError, ValueError) as err:
        print(f'Failed to access I2C bus: {err}')
        return
    from simoc_sam.sensors.utils import I2C_TO_SENSOR
    devices = i2c.scan()
    if not devices:
        print('No sensors found.')
        return
    print(f'Found {len(devices)} sensors:')
    for i2c_addr in devices:
        if i2c_addr in I2C_TO_SENSOR:
            sensor_name = I2C_TO_SENSOR[i2c_addr].name
        else:
            sensor_name = '<unknown>'
        print(f'* {sensor_name} (I2C addr: {i2c_addr:#x})')


# Combined info
def print_network_info():
    print_hostname()
    if netifaces:
        print_addresses()
        print_batman()
    else:
        print("Can't import the netifaces module.")

def print_sensors_info():
    print_MCP2221_info()
    print_sensors()

def print_info():
    print('===== Network info =====')
    print_network_info()
    print('===== Sensors info =====')
    print_sensors_info()

if __name__ == '__main__':
    print_info()
