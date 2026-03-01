import re
import socket
import pathlib
import subprocess

from collections import defaultdict

try:
    import netifaces
except ImportError:
    netifaces = None

CONFIGS_DIR = pathlib.Path(__file__).resolve().parent / 'configs'
SYSTEMD_SYSTEM_DIR = pathlib.Path('/etc/systemd/system')

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
    from simoc_sam import utils
    try:
        addresses = utils.get_i2c_addresses()
    except RuntimeError as err:
        print(f'Sensor scanning failed: {err}')
        return
    if not addresses:
        print('No sensors found.')
        return
    print(f'Found {len(addresses)} sensors:')
    for addr in addresses:
        name = utils.i2c_to_device_name(addr)
        print(f'* {name} (I2C addr: {addr:x})')


# Services info

def get_boot_start_services():
    """Return a set of service names that will start on boot."""
    # note: checking is-enabled is not enough to ensure boot start
    boot_services = set()
    targets = ['multi-user', 'graphical']  # common systemd targets
    for target in targets:
        # files in these directories indicate services that start on boot
        wants_dir = SYSTEMD_SYSTEM_DIR / f'{target}.target.wants'
        if wants_dir.is_dir():
            for entry in wants_dir.iterdir():
                if entry.suffix == '.service':
                    boot_services.add(entry.stem)  # add without .service suffix
    return boot_services

def check_journal_errors(service_name, n_lines=15):
    """Check for errors in the journal output of the given service."""
    try:
        cmd = ['journalctl', '-u', service_name, '-n', str(n_lines), '--no-pager']
        result = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:
        print(f"Error checking journal for {service_name!r}: {e}")
        return True
    output = result.stdout.lower()
    error_indicators = ['error', 'failed', 'exception', 'traceback', 'critical']
    return any(indicator in output for indicator in error_indicators)

def get_services_info(services=None):
    """Get info about the given systemd services using systemctl show."""
    if services:
        # if service is a template use a wildcard to get all instances
        services = [service.replace('@', '@*') for service in services]
    else:
        services = ['*.service']  # get all services if services is empty
    try:
        cmd = ['systemctl', 'show', *services, '--no-pager',
               '--property=Id,ActiveState,UnitFileState']
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return {}
        boot_services = get_boot_start_services()
        all_services = defaultdict(list)
        for service in result.stdout.strip().split('\n\n'):
            info = dict(prop.split('=') for prop in service.split('\n'))
            name = info['Id'].removesuffix('.service')
            all_services[re.sub('@.*$', '@', name)].append({
                'name': name,
                'state': info['ActiveState'],
                'is_active': info['ActiveState'] == 'active',
                'enabled': info['UnitFileState'],
                'is_enabled': info['UnitFileState'] == 'enabled',
                'starts_on_boot': name in boot_services,
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
    all_services = get_services_info(services_to_check)
    active_services = []
    inactive_services = []
    # separate services in two groups to show inactive services last
    for name, services in sorted(all_services.items()):
        if len(services) == 1 and not services[0]['is_active']:
            inactive_services.append((name, services))
        else:
            active_services.append((name, services))
    services_with_errors = []
    state_icons = dict(active='🟢', inactive='⚫', activating='🟡',
                       deactivating='🟡', reloading='🟡', failed='🔴')
    active_icons = dict(enabled='🟢', disabled='🔴', linked='🟢', static='⚫')
    print('Service name              | Active         | Enabled    | Boot | Errors')
    print('--------------------------+----------------+------------+------+--------')
    for group in [active_services, inactive_services]:
        for name, services in group:
            indent = ''
            if len(services) > 1:
                # for service templates only print the template name
                print(f'{name:<25} |                |            |      |')
                indent = '  '
            for service in services:
                service_name = f'{indent}{service["name"]:<{25-len(indent)}}'
                active_icon = state_icons.get(service['state'], '🔴')
                enabled_icon = active_icons.get(service['enabled'], '🔴')
                boot_icon = '🟢' if service['starts_on_boot'] else '⚫'
                error_icon = '🛑' if service['has_errors'] else ''
                if service['has_errors']:
                    services_with_errors.append(service['name'])
                print(f'{service_name} | {active_icon}{service["state"]:<12} | '
                    f'{enabled_icon}{service["enabled"]:<8} | {boot_icon:3} | {error_icon}')
        print('--------------------------+----------------+------------+------+--------')
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
