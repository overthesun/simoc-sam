"""Script to setup and run SIMOC-SAM."""

import os
import re
import sys
import uuid
import shutil
import socket
import pathlib
import argparse
import tempfile
import functools
import subprocess

try:
    from jinja2 import Template
except ModuleNotFoundError:
    # keep running if jinja2 is missing
    Template = None

SIMOC_SAM_DIR = pathlib.Path(__file__).resolve().parent
CONFIGS_DIR = SIMOC_SAM_DIR / 'configs'
SYSTEMD_DIR = pathlib.Path('/etc/systemd/system')
NM_DIR = pathlib.Path('/etc/NetworkManager/system-connections/')
NM_TMPL = CONFIGS_DIR / 'nmconnection.tmpl'
HOTSPOT_CFG = 'hotspot.nmconnection'
WIFI_CFG = 'wifi.nmconnection'
VENV_DIR = SIMOC_SAM_DIR / 'venv'
VENV_PY = str(VENV_DIR / 'bin' / 'python3')
DEPS = 'requirements.txt'
DEV_DEPS = 'dev-requirements.txt'
TMUX_SNAME = 'SAM'  # tmux session name
HOSTNAME = socket.gethostname()

COMMANDS = {}

def cmd(func):
    """Decorator to add commands to the COMMANDS dict."""
    COMMANDS[func.__name__] = func
    return func

def run(args, **kwargs):
    print('>>', ' '.join(args))
    print('-'*80)
    result = subprocess.run(args, **kwargs)
    print('-'*80)
    print('<<', result)
    print()
    return not result.returncode

def needs_venv(func):
    """Ensure that the venv exist before calling func."""
    @functools.wraps(func)
    def inner(*args, **kwargs):
        if not VENV_DIR.exists():
            print('venv dir missing -- creating it')
            create_venv()
        return func(*args, **kwargs)
    return inner

def needs_root(func):
    """Ensure that the command is run as root before calling func."""
    @functools.wraps(func)
    def inner(*args, **kwargs):
        if os.geteuid() != 0:
            os.execvp('sudo', ['sudo', sys.executable, *sys.argv])
            return
        else:
            return func(*args, **kwargs)
    return inner

def write_template(path, replacements):
    """Replace {{placeholders}} in a file with the given replacements."""
    template = Template(path.read_text())
    path.write_text(template.render(replacements))

@cmd
def create_venv():
    """Create and set up a virtualenv."""
    if VENV_DIR.exists():
        print('venv already exists -- aborting.')
        return
    return (
        run([sys.executable, '-m', 'venv', 'venv']) and
        run([VENV_PY, '-m', 'pip', 'install', '--upgrade', 'pip']) and
        run([VENV_PY, '-m', 'pip', 'install', '-r', DEPS]) and
        run([VENV_PY, '-m', 'pip', 'install', '-r', DEV_DEPS]) and
        run([VENV_PY, '-m', 'pip', 'install', '-e', '.'])
    )

@cmd
def clean_venv():
    """Remove the venv dir."""
    if not VENV_DIR.exists():
        print(f'No venv dir found -- aborting.')
        return
    print(f'Removing venv dir: {VENV_DIR}')
    shutil.rmtree(VENV_DIR)
    print('venv dir removed.')

target_re = re.compile(r'^(?:([^@]+)@)?([^:]+)(?::([^:]+))?$')
ipv4_re = re.compile(r'^\d+\.\d+\.\d+\.\d+$')  # does it look like an IPv4?
@cmd
def copy_repo(target, *, exclude_venv=True, exclude_git=True):
    """Copy the repository to a remote host using rsync."""
    user, host, path = target_re.fullmatch(target).groups()
    user = user or 'pi'
    path = path or '/home/pi/simoc-sam'
    repo = f'{pathlib.Path(__file__).parent}/'  # rsync wants the trailing /
    excludes = ['--exclude', '**/__pycache__']
    if exclude_venv:
        excludes.extend(['--exclude', 'venv'])
    if exclude_git:
        excludes.extend(['--exclude', '.git'])
    def rsync_cmd(user, host, path):
        return ['rsync', '-avz', *excludes, repo, f'{user}@{host}:{path}']
    try:
        subprocess.run(rsync_cmd(user, host, path),
                       check=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as err:
        stderr = err.stderr.decode('utf-8')
        if (('failure in name resolution' in stderr or
             'Could not resolve hostname' in stderr) and
            not ipv4_re.fullmatch(host) and not host.endswith('.local')):
            print(f'Failed to resolve <{host}>.')
            host += '.local'
            print(f'Retrying with <{host}>...')
            subprocess.run(rsync_cmd(user, host, path))
        else:
            print(stderr)

@cmd
def copy_repo_venv(target):
    """Copy the repository to a remote host using rsync (includes venv dir)."""
    copy_repo(target, exclude_venv=False)

@cmd
def copy_repo_git(target):
    """Copy the repository to a remote host using rsync (includes .git dir)."""
    copy_repo(target, exclude_git=False)


host_re = re.compile(r'^samrpi(\d+)$')
address_re = re.compile(r'^(\s*address\s+)((\d+\.\d+.\d+.)(\d+))(\s*)$')
@cmd
def fix_ip():
    """Ensure that the bat0 IP matches the hostname."""
    bat0 = pathlib.Path('/etc/network/interfaces.d/bat0')
    hostname = socket.gethostname()
    if match := host_re.fullmatch(hostname):
        hostnum = match[1]  # extract e.g. '1' from 'samrpi1'
    else:
        print('Invalid hostname (should be "samrpiN").')
        return
    updated = False
    new_bat0 = []
    with open(bat0) as file:
        for line in file:
            if match := address_re.fullmatch(line):
                head, curr_ip, three_octs, last_oct, tail = match.groups()
                new_ip = three_octs + hostnum  # update last octet
                if new_ip != curr_ip:
                    updated = True
                new_bat0.append(head + new_ip + tail)
            else:
                new_bat0.append(line)
    # rewrite the file and reboot if the IP needs to be updated
    if updated:
        print(f'Updating <{bat0}>...')
        with open(bat0, 'w') as file:
            file.writelines(new_bat0)
        print(f'IP address in <{bat0}> updated from <{curr_ip}> to <{new_ip}>.')
        print('Restarting...')
        subprocess.run(['sudo', 'reboot'])


@cmd
@needs_root
def setup_hotspot(interface='wlan0', ssid='SIMOC', password='simoc123'):
    """Setup a hotspot that allows direct connections to the RPi."""
    hotspot_nmconn = NM_DIR / HOTSPOT_CFG
    if hotspot_nmconn.exists():
        print('Hotspot already set up.  Use `teardown-hotspot` to remove.')
        return
    repls = dict(
        conn_id='hotspot', conn_uuid=uuid.uuid4(), conn_interface=interface,
        wifi_mode='ap', wifi_ssid=ssid, wifi_pass=password, wifi_extra='band=bg\n',
        ipv4_method='shared',
    )
    setup_nmconn(hotspot_nmconn, repls)

@cmd
@needs_root
def teardown_hotspot():
    """Revert the changes made by the setup-hotspot command."""
    teardown_nmconn(NM_DIR / HOTSPOT_CFG)


@cmd
@needs_root
def setup_wifi(ssid=None, password=None, interface='wlan0'):
    """Setup a connection to an existing WiFi network."""
    wifi_nmconn = NM_DIR / WIFI_CFG
    if wifi_nmconn.exists():
        print('WiFi connection already set up.  Use `teardown-wifi` to remove.')
        return
    if ssid is None or password is None:
        print('Please provide the SSID and the password.')
        return
    repls = dict(
        conn_id='wifi', conn_uuid=uuid.uuid4(), conn_interface=interface,
        wifi_mode='infrastructure', wifi_ssid=ssid, wifi_pass=password,
        ipv4_method='auto',
    )
    setup_nmconn(wifi_nmconn, repls)

@cmd
@needs_root
def teardown_wifi():
    """Revert the changes made by the setup-wifi command."""
    teardown_nmconn(NM_DIR / WIFI_CFG)


def setup_nmconn(nmconn_file, repls):
    # copy the template in the NetworkManager dir
    shutil.copy(NM_TMPL, nmconn_file)
    # update template with actual values and set permissions/owner
    write_template(nmconn_file, repls)
    nmconn_file.chmod(0o600)
    os.chown(nmconn_file, 0, 0)  # owner is now root
    if not run(['systemctl', 'is-enabled', 'NetworkManager']):
        run(['systemctl', 'enable', 'NetworkManager'])
    run(['systemctl', 'restart', 'NetworkManager'])

def teardown_nmconn(nmconn_file):
    """Remove the given nmconn file and possibly stop NetworkManager."""
    nmconn_file.unlink(missing_ok=True)
    if not os.listdir(NM_DIR):
        # stop NetworkManager if there are no other connections
        run(['systemctl', 'stop', 'NetworkManager'])
        run(['systemctl', 'disable', 'NetworkManager'])


@cmd
@needs_root
def setup_mqttbridge():
    """Setup a systemd service that runs the mqttbridge."""
    setup_systemd_service('mqttbridge')

@cmd
@needs_root
def teardown_mqttbridge():
    """Revert the changes made by the setup-mqttbridge command."""
    teardown_systemd_service('mqttbridge')


def setup_systemd_service(name):
    # create a symlink to the given service, enable it, and start it
    service_name = f'{name}.service'
    (SYSTEMD_DIR / service_name).symlink_to(CONFIGS_DIR / service_name)
    if not run(['systemctl', 'is-enabled', name]):
        run(['systemctl', 'enable', name])
    if not run(['systemctl', 'is-active', name]):
        run(['systemctl', 'start', name])

def teardown_systemd_service(name):
    # stop, disable, and remove the symlink to the given service
    run(['systemctl', 'stop', name])
    run(['systemctl', 'disable', name])
    pathlib.Path(SYSTEMD_DIR / f'{name}.service').unlink(missing_ok=True)


@cmd
@needs_root
def setup_nginx():
    """Setup nginx to serve the frontend and the socketio backend."""
    if not shutil.which('nginx'):
        sys.exit('nginx not found. Install it with `sudo apt install nginx`.')
    # remove default site and add simoc_live site
    sites_enabled = pathlib.Path('/etc/nginx/sites-enabled/')
    default = sites_enabled / 'default'
    if default.exists():
        default.unlink()  # remove default site
    simoc_live_tmpl = CONFIGS_DIR / 'simoc_live.tmpl'
    simoc_live = CONFIGS_DIR / 'simoc_live'
    shutil.copy(simoc_live_tmpl, simoc_live)
    write_template(simoc_live, dict(hostname=HOSTNAME))  # update hostname
    (sites_enabled / 'simoc_live').symlink_to(simoc_live)
    assert run(['nginx', '-t'])  # ensure that the config is valid
    # enable/start nginx
    if not run(['systemctl', 'is-enabled', 'nginx']):
        run(['systemctl', 'enable', 'nginx'])
    if not run(['systemctl', 'is-active', 'nginx']):
        run(['systemctl', 'start', 'nginx'])

@cmd
@needs_root
def teardown_nginx():
    """Revert the changes made by the setup-nginx command."""
    run(['systemctl', 'stop', 'nginx'])
    run(['systemctl', 'disable', 'nginx'])
    pathlib.Path('/etc/nginx/sites-enabled/simoc_live').unlink(missing_ok=True)


@cmd
@needs_venv
def test(*args):
    """Run the tests."""
    pytest = str(VENV_DIR / 'bin' / 'pytest')
    return run([pytest, '-v', *args])

@cmd
@needs_venv
def run_server():
    """Run the sioserver."""
    run([VENV_PY, '-m', 'simoc_sam.sioserver'])

@cmd
@needs_venv
def run_tmux(file='mqtt'):
    """Launch a tmux script (or attach to an existing session)."""
    if run(['tmux', 'has-session', '-t', TMUX_SNAME]):
        run(['tmux', 'attach-session', '-t', TMUX_SNAME])  # attach to sessions
    else:
        tmux_path = SIMOC_SAM_DIR / 'tmux' / f'{file}.sh'
        run([str(tmux_path), TMUX_SNAME])  # start new sessions


@cmd
@needs_venv
def info():
    """Print host info about the network and sensors."""
    import hostinfo
    hostinfo.print_info()

@cmd
@needs_venv
def network_info():
    """Print info about the network (hostname, addresses)."""
    import hostinfo
    hostinfo.print_network_info()

@cmd
@needs_venv
def sensors_info():
    """Print info about the connected sensors."""
    import hostinfo
    hostinfo.print_sensors_info()

@cmd
def hosts(target=None):
    """Print info about the other hosts in the network."""
    import netinfo
    netinfo.print_info(target)


VERNIER_USB_RULES = """\
SUBSYSTEM=="usb", ATTRS{idVendor}=="08f7", MODE="0666"
SUBSYSTEM=="usb_device", ATTRS{idVendor}=="08f7", MODE="0666"
"""
MCP2221_RULE = """\
SUBSYSTEM=="usb", ATTRS{idVendor}=="04d8", ATTR{idProduct}=="00dd", MODE="0666"
"""
USB_RULES_DIR = '/etc/udev/rules.d/'

@cmd
def add_vernier_rules():
    """Add Linux-specific USB rules for Vernier sensors access."""
    vernier_fname = 'vstlibusb.rules'
    with open(vernier_fname, 'w') as f:
        f.write(VERNIER_USB_RULES)
    return run(['sudo', 'mv', vernier_fname, USB_RULES_DIR])

@cmd
def add_mcp_rules():
    """Add Linux-specific USB rules for Adafruit MCP2221 access."""
    mcp_fname = '99-mcp2221.rules'
    with open(mcp_fname, 'w') as f:
        f.write(MCP2221_RULE)
    return run(['sudo', 'mv', mcp_fname, USB_RULES_DIR])

@cmd
def add_usb_rules():
    """Add Linux-specific rules for USB devices access."""
    return add_vernier_rules() and add_mcp_rules()


@cmd
@needs_root
def install_touchscreen():
    """Install the GeeekPi 3.5" LCD touchscreen."""
    repo_name = 'LCD-show'
    repo_url = f'https://github.com/goodtft/{repo_name}.git'
    with tempfile.TemporaryDirectory() as tmpdir_name:
        os.chdir(tmpdir_name)
        repo_path = pathlib.Path(tmpdir_name) / repo_name
        run(['git', 'clone', repo_url, str(repo_path)])  # clone repo
        run(['chmod', '-R', '775', str(repo_path)])  # fix permissions
        run([str(repo_path / 'MHS35-show')])  # install the screen and reboot


def create_help(cmds):
    help = ['Full list of available commands:']
    for cmd, func in cmds.items():
        help.append(f'{cmd.replace("_", "-"):18} {func.__doc__}')
    return '\n'.join(help)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Setup and run SIMOC-SAM.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('cmd', metavar='CMD', help=create_help(COMMANDS))
    parser.add_argument('args', metavar='*ARGS', nargs='*',
                        help='Additional optional args to be passed to CMD.')
    args = parser.parse_args()

    cmd = args.cmd.replace('-', '_')
    if cmd in COMMANDS:
        result = COMMANDS[cmd](*args.args)
        parser.exit(not result)
    else:
        cmds = ', '.join(cmd.replace('_', '-') for cmd in COMMANDS.keys())
        parser.error(f'Command not found.  Available commands: {cmds}')
