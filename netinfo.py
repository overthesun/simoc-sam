import re
import subprocess

TARGET = '172.27.0.0/24'
# TARGET = '192.168.1.0/24'
# TARGET = '172.27.0.1-10'

def find_hosts(target):
    """Do an nmap ping sweep and report found hosts for the given target."""
    # target can also be a range like 172.27.0.1-10
    cmd = ['nmap', '-sn', '-oG', '-', target]
    output = subprocess.check_output(cmd).decode('utf-8')
    ips = {}
    for line in output.splitlines():
        if line.startswith('#'):
            continue
        if line.startswith('Host'):
            # line looks like `Host: 172.27.0.1 ()     Status: Up`
            _, ip, *_, status = line.split()
            ips[ip] = dict(status=status)
    return ips

arp_re = re.compile('\(([0-9.]+)\) at ([0-9a-f:]+) \[[^]]+\] on (\w+)')

def find_MACs(ips):
    """Use arp to find interfaces and MACs of the given IPs."""
    # note: you need to call find_hosts() first to populate the arp cache
    output = subprocess.check_output(['arp', '-an']).decode('utf-8')
    for ip, mac, iface in arp_re.findall(output):
        if ip not in ips:
            continue
        ips[ip]['mac'] = mac
        ips[ip]['iface'] = iface
    for data in ips.values():
        if 'mac' not in data:
            data['mac'] = '???'
            data['iface'] = '???'
    return ips

def find_hostnames(ips):
    """Use avahi to resolve local hostnames of the given IPs."""
    for ip, data in ips.items():
        cmd = ['avahi-resolve-address', ip]
        output = subprocess.check_output(cmd).decode('utf-8')
        if output:
            ip, hostname = output.split()
            data['hostname'] = hostname
        else:
            data['hostname'] = '???'
    return ips

def format_ips(ips):
    """Format all the data in a table"""
    # determine column widths
    ipw = max(len(ip) for ip in ips)
    hostw = max(max(len(data['hostname']) for data in ips.values()), 8)
    statw = max(max(len(data['status']) for data in ips.values()), 6)
    ifacew = max(max(len(data['iface']) for data in ips.values()), 9)
    macw = max(max(len(data['mac']) for data in ips.values()), 3)
    # build and print table
    sep = '+'.join(['', '-'*(ipw+2), '-'*(hostw+2), '-'*(statw+2),
                    '-'*(ifacew+2), '-'*(macw+2), ''])
    print(sep)
    print(f'| {"IP":^{ipw}} | {"Hostname":^{hostw}} | {"Status":^{statw}} | '
          f'{"Interface":^{ifacew}} | {"MAC":^{macw}} |')
    print(sep)
    for ip, data in ips.items():
        print(f'| {ip:{ipw}} | {data["hostname"]:>{hostw}} | '
              f'{data["status"]:^{statw}} | {data["iface"]:^{ifacew}} | '
              f'{data["mac"]:^{macw}} |')
    print(sep)

def print_info(target=None):
    """Collect and print network information."""
    if target is None:
        target = TARGET
    print(f'Scanning <{target}> (might take a few seconds)...')
    ips = find_hosts(target)
    if not ips:
        print(f'No devices found for <{target}>.')
        return
    ips = find_MACs(ips)
    ips = find_hostnames(ips)
    format_ips(ips)
    return ips

if __name__ == '__main__':
    print_info(TARGET)
