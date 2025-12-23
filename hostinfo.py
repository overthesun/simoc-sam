import os
import re
import socket
import pathlib
import subprocess

from collections import defaultdict

try:
    import netifaces
except ImportError:
    netifaces = None

# Get the configs directory path
CONFIGS_DIR = pathlib.Path(__file__).resolve().parent / 'configs'

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

def print_MCP2221_info():
    """Print True if the MCP2221 is connected, False otherwise."""
    from simoc_sam.sensors import utils
    print(f'MCP2221 connected: {utils.has_mcp2221()}')

def print_sensors():
    """Print a list of connected sensors and their I2C addresses."""
    from simoc_sam.sensors import utils

    try:
        board = utils.import_board()
    except (ImportError, OSError) as err:
        print(f'Sensor scanning failed: {err}')
        return  # doesn't always work with RPi + MCP2221
    import busio
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
    except (AttributeError, ValueError) as err:
        print(f'Failed to access I2C bus: {err}')
        return
    devices = i2c.scan()
    if not devices:
        print('No sensors found.')
        return
    print(f'Found {len(devices)} sensors:')
    for i2c_addr in devices:
        if i2c_addr in utils.I2C_TO_SENSOR:
            sensor_name = utils.I2C_TO_SENSOR[i2c_addr].name
        else:
            sensor_name = '<unknown>'
        print(f'* {sensor_name} (I2C addr: {i2c_addr:#x})')


# Services info

def check_service_enabled_properly(service_name):
    """Check if a service is properly enabled by verifying multi-user.target.wants symlink.
    
    Uses 'systemctl is-enabled --full' to check if the service has a symlink in
    /etc/systemd/system/multi-user.target.wants/, which is required for the service
    to actually start on boot.
    """
    try:
        cmd = ['systemctl', 'is-enabled', '--full', f'{service_name}.service']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # If the command fails, the service is not enabled
        if result.returncode != 0:
            return False
            
        # Check if the output contains the multi-user.target.wants symlink
        return '/etc/systemd/system/multi-user.target.wants/' in result.stdout
        
    except Exception as e:
        print(f"Error checking if {service_name} is properly enabled: {e}")
        return False


def check_journal_errors(service_name, n_lines=15):
    """Check for errors in the journal output of the given service."""
    try:
        cmd = ['journalctl', '-u', service_name, '-n', str(n_lines), '--no-pager']
        cp = subprocess.run(cmd , capture_output=True, text=True)
    except Exception as e:
        print(f"Error checking journal for {service_name!r}: {e}")
        return True
    output = cp.stdout.lower()
    error_indicators = ['error', 'failed', 'exception', 'traceback', 'critical']
    return any(indicator in output for indicator in error_indicators)


def get_all_running_services():
    """Get all running systemd services using systemctl show."""
    try:
        cmd = ['systemctl', 'show', '*.service', '--state=running',
               '--no-pager', '--property=Id,ActiveState,UnitFileState']
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return {}
        all_services = defaultdict(list)
        for service in result.stdout.strip().split('\n\n'):
            info = dict(prop.split('=') for prop in service.split('\n'))
            name = info['Id'].removesuffix('.service')
            all_services[re.sub('@.*$', '@', name)].append({
                'name': name,
                'state': info['ActiveState'],
                'is_active': info['ActiveState'] == 'active',
                'enabled': info['UnitFileState'],
                'is_enabled': check_service_enabled_properly(name),
                'has_errors': check_journal_errors(info['Id']),
            })
        return all_services
    except Exception as e:
        print(f"Error getting running services: {e}")
        return {}

def print_services():
    """Print status of SIMOC Live services and key system services."""
    config_services = [service_file.stem for service_file in CONFIGS_DIR.glob('*.service')]
    system_services = ['systemd-timesyncd', 'chrony', 'mosquitto', 'avahi-daemon']
    services_to_check = config_services + system_services

    all_services = get_all_running_services()
    filtered_services = {name: info for name, info in all_services.items()
                         if name in services_to_check}
    inactive_services = set(services_to_check) - filtered_services.keys()
    services_with_errors = []

    print('Service name              | Active         | Enabled    | Errors')
    print('--------------------------+----------------+------------+--------')
    for name, services in sorted(filtered_services.items()):
        indent = ''
        if len(services) > 1:
            # for service templates only print the template name
            print(f'{name:<25} |                |            |')
            indent = '  '
        for service in services:
            service_name = f'{indent}{service["name"]:<{25-len(indent)}}'
            active_icon = '🟢' if service['is_active'] else '🔴'
            enabled_icon = '🟢' if service['is_enabled'] else '🔴'
            error_icon = '⚠️' if service['has_errors'] else ''
            if service['has_errors']:
                services_with_errors.append(service['name'])
            print(f'{service_name} | {active_icon}{service["state"]:<12} | '
                  f'{enabled_icon}{service["enabled"]:<8} | {error_icon}')
    print('--------------------------+----------------+------------+--------')

    if inactive_services:
        print('* Inactive services:', ', '.join(sorted(inactive_services)))

    if services_with_errors:
        print(f'* {len(services_with_errors)} service(s) with errors. '
              f'Run the following command(s) to see the logs:')
        for service_name in services_with_errors:
            print(f'  journalctl -u {service_name} --no-pager -n 100')


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
    print('\n===== Sensors info =====')
    print_sensors_info()
    print('\n===== Services info =====')
    print_services()

if __name__ == '__main__':
    print_info()
