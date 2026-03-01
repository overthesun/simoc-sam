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

try:
    from simoc_sam import config
except ModuleNotFoundError:
    # keep running if simoc_sam is not installed yet
    config = None


HOME = pathlib.Path.home()
SIMOC_SAM_DIR = pathlib.Path(__file__).resolve().parent
CONFIGS_DIR = SIMOC_SAM_DIR / 'configs'
SYSTEMD_DIR = pathlib.Path('/etc/systemd/system')
NM_DIR = pathlib.Path('/etc/NetworkManager/system-connections/')
NM_TMPL = CONFIGS_DIR / 'nmconnection.tmpl'
MOSQUITTO_DIR = pathlib.Path('/etc/mosquitto/conf.d/')
HOTSPOT_CONN = 'hotspot'
WIFI_CONN = 'wifi'
VENV_DIR = SIMOC_SAM_DIR / 'venv'
VENV_PY = str(VENV_DIR / 'bin' / 'python3')
DEPS = SIMOC_SAM_DIR / 'requirements.txt'
DEV_DEPS = SIMOC_SAM_DIR / 'dev-requirements.txt'
TMUX_SNAME = 'SAM'  # tmux session name
HOSTNAME = socket.gethostname()

APT_INSTALL = ['nmap', 'vim', 'tcpdump', 'tmux', 'nginx',
               'mosquitto', 'mosquitto-clients', 'avahi-utils']
APT_REMOVE = ['chromium']

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
            os.execvp('sudo', ['sudo', '--preserve-env=HOME',
                               sys.executable, *sys.argv])
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
        run([sys.executable, '-m', 'venv', str(VENV_DIR)]) and
        run([VENV_PY, '-m', 'pip', 'install', '--upgrade', 'pip']) and
        run([VENV_PY, '-m', 'pip', 'install', '-r', str(DEPS)]) and
        run([VENV_PY, '-m', 'pip', 'install', '-r', str(DEV_DEPS)]) and
        run([VENV_PY, '-m', 'pip', 'install', '-e', str(SIMOC_SAM_DIR)])
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


@cmd
def update():
    """Update the code to the latest version."""
    # get the current branch
    try:
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                         cwd=SIMOC_SAM_DIR, text=True).strip()
    except subprocess.CalledProcessError:
        print(f'Error: Failed to get the current branch.')
        return False
    # perform git pull
    print(f'Updating code to the latest version (current branch: {branch!r}).')
    success = run(['git', 'pull', 'origin', branch], cwd=SIMOC_SAM_DIR)
    if success:
        print('Code updated successfully.')
    else:
        print('Update failed: see error log above for details.')
    return success


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
    hotspot_nmconn = NM_DIR / f'{HOTSPOT_CONN}.nmconnection'
    if hotspot_nmconn.exists():
        print('Hotspot already set up.  Use `teardown-hotspot` to remove.')
        return
    repls = dict(
        conn_id=HOTSPOT_CONN, conn_uuid=uuid.uuid4(), conn_interface=interface,
        wifi_mode='ap', wifi_ssid=ssid, wifi_pass=password, wifi_extra='band=bg\n',
        ipv4_method='shared',
    )
    setup_nmconn(hotspot_nmconn, repls)

@cmd
@needs_root
def teardown_hotspot():
    """Revert the changes made by the setup-hotspot command."""
    teardown_nmconn(HOTSPOT_CONN)


@cmd
@needs_root
def setup_wifi(ssid=None, password=None, interface='wlan0'):
    """Setup a connection to an existing WiFi network."""
    wifi_nmconn = NM_DIR / f'{WIFI_CONN}.nmconnection'
    if wifi_nmconn.exists():
        print('WiFi connection already set up.  Use `teardown-wifi` to remove.')
        return
    if ssid is None or password is None:
        print('Please provide the SSID and the password.')
        return
    repls = dict(
        conn_id=WIFI_CONN, conn_uuid=uuid.uuid4(), conn_interface=interface,
        wifi_mode='infrastructure', wifi_ssid=ssid, wifi_pass=password,
        ipv4_method='auto',
    )
    setup_nmconn(wifi_nmconn, repls)

@cmd
@needs_root
def teardown_wifi():
    """Revert the changes made by the setup-wifi command."""
    teardown_nmconn(WIFI_CONN)


def setup_nmconn(nmconn_file, repls):
    """Create and activate a NetworkManager connection."""
    # copy the template in the NetworkManager dir
    shutil.copy(NM_TMPL, nmconn_file)
    # update template with actual values and set permissions/owner
    write_template(nmconn_file, repls)
    nmconn_file.chmod(0o600)
    os.chown(nmconn_file, 0, 0)  # owner is now root
    if not run(['systemctl', 'is-enabled', 'NetworkManager']):
        run(['systemctl', 'enable', 'NetworkManager'])
    run(['nmcli', 'radio', 'wifi', 'on'])  # ensure wifi is on
    # reload connections (will auto-activate if interface is available)
    run(['nmcli', 'connection', 'reload'])

def teardown_nmconn(conn_id):
    """Stop and remove the given NetworkManager connection."""
    run(['nmcli', 'connection', 'delete', conn_id])


@cmd
@needs_root
def setup_mosquitto():
    """Setup and configure a local Mosquitto MQTT broker."""
    if not shutil.which('mosquitto'):
        sys.exit('Mosquitto not found. Install it with `sudo apt install mosquitto`.')
    mosquitto_conf_src = CONFIGS_DIR / 'mosquitto-local.conf'
    mosquitto_conf_dest = MOSQUITTO_DIR / 'simoc-sam.conf'
    if mosquitto_conf_dest.exists():
        print(f'{mosquitto_conf_dest} already exists -- recreating it...')
        mosquitto_conf_dest.unlink()
    shutil.copy(mosquitto_conf_src, mosquitto_conf_dest)
    mosquitto_conf_dest.chmod(0o644)
    os.chown(mosquitto_conf_dest, 0, 0)  # owner is now root
    print(f'Mosquitto configuration deployed to {mosquitto_conf_dest}')
    if (run(['systemctl', 'enable', 'mosquitto']) and
        run(['systemctl', 'restart', 'mosquitto'])):
        print('Mosquitto service enabled and started.')
    else:
        print('Failed to enable/start mosquitto service. Check logs with:')
        print('  journalctl -u mosquitto -n 50')

@cmd
@needs_root
def teardown_mosquitto():
    """Revert the changes made by the setup-mosquitto command."""
    run(['systemctl', 'stop', 'mosquitto'])
    run(['systemctl', 'disable', 'mosquitto'])
    print('Mosquitto service stopped and disabled.')
    mosquitto_conf_dest = MOSQUITTO_DIR / 'simoc-sam.conf'
    mosquitto_conf_dest.unlink(missing_ok=True)


def setup_systemd_unit(name, unit_type='service', enable=True, start=True):
    """Setup a systemd unit by creating symlink and optionally enabling/starting."""
    unit_name = f'{name}.{unit_type}'
    if '@' in name:
        # handle templates, e.g. sensor-runner@scd30 -> sensor-runner@.service
        target_name = f'{name.split("@")[0]}@.{unit_type}'
    else:
        target_name = unit_name
    target_path = CONFIGS_DIR / target_name
    unit_path = SYSTEMD_DIR / unit_name
    if unit_path.exists():
        print(f'{unit_path} already exists -- recreating it...')
        unit_path.unlink()
    unit_path.symlink_to(target_path)
    print(f'Created symlink {unit_path} → {target_path}.')
    if enable:
        run(['systemctl', 'enable', unit_name])
    if start:
        run(['systemctl', 'start', unit_name])

def teardown_systemd_unit(name, unit_type='service', stop=True, disable=True):
    """Optionally stop/disable the unit and then remove the symlink."""
    unit_name = f'{name}.{unit_type}'
    if stop:
        run(['systemctl', 'stop', unit_name])
    if disable:
        run(['systemctl', 'disable', unit_name])
    pathlib.Path(SYSTEMD_DIR / unit_name).unlink(missing_ok=True)


@cmd
@needs_root
def setup_or_teardown_sensors(function, sensors=None):
    """Setup systemd services that run the sensors."""
    if sensors:
        sensors = sensors.split(',')
    else:
        sensors = config.sensors
    for sensor in sensors:
        function(f'sensor-runner@{sensor}')

@cmd
@needs_root
def setup_sensors(sensors=None):
    """Setup systemd services that run the sensors."""
    setup_or_teardown_sensors(setup_systemd_unit, sensors)

@cmd
@needs_root
def teardown_sensors(sensors=None):
    """Revert the changes made by the setup-sensors command."""
    setup_or_teardown_sensors(teardown_systemd_unit, sensors)

@cmd
@needs_root
def setup_or_teardown_display(function, display=None):
    """Setup/teardown systemd service that runs the display."""
    if display is None:
        display = config.display
    if not display:
        print('No display specified -- aborting.')
        return
    function(f'display-runner@{display}')

@cmd
@needs_root
def setup_display(display=None):
    """Setup systemd service that runs the display."""
    setup_or_teardown_display(setup_systemd_unit, display)

@cmd
@needs_root
def teardown_display(display=None):
    """Revert the changes made by the setup-display command."""
    setup_or_teardown_display(teardown_systemd_unit, display)


@cmd
@needs_root
def setup_siobridge():
    """Setup a systemd service that runs the siobridge."""
    setup_systemd_unit('siobridge')

@cmd
@needs_root
def teardown_siobridge():
    """Revert the changes made by the setup-siobridge command."""
    teardown_systemd_unit('siobridge')


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
    dist_dir = config.simoc_web_dist_dir
    write_template(simoc_live, dict(hostname=HOSTNAME, dist_dir=dist_dir))
    (sites_enabled / 'simoc_live').symlink_to(simoc_live)
    assert run(['nginx', '-t'])  # ensure that the config is valid
    # enable/start/reload nginx
    if not run(['systemctl', 'is-enabled', 'nginx']):
        run(['systemctl', 'enable', 'nginx'])
    if not run(['systemctl', 'is-active', 'nginx']):
        run(['systemctl', 'start', 'nginx'])
    else:
        run(['systemctl', 'reload', 'nginx'])  # reload to apply new config

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
def services_info():
    """Print status of SIMOC Live services and key system services."""
    import hostinfo
    hostinfo.print_services()

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
        repo_path = pathlib.Path(tmpdir_name) / repo_name
        script_path = repo_path / 'MHS35-show'
        run(['git', 'clone', repo_url, str(repo_path)])  # clone repo
        os.chdir(repo_path)  # the script creates files in the cwd
        run(['sed', '-i', '-e', '/hdmi_cvt / s/480 320/960 640/',
             str(script_path)])  # update res (also: fbset -xres 960 -yres 640)
        run(['chmod', '-R', '775', str(repo_path)])  # fix permissions
        run([str(script_path)])  # install the screen and reboot

@cmd
def initial_setup():
    """Perform the initial setup of the Raspberry Pi."""
    print('Installing bash aliases...')
    install_bash_aliases()
    print('Removing empty home dirs...')
    remove_home_dirs()
    print('Enabling i2c...')
    enable_i2c()
    print('Setting up locale...')
    setup_locale()
    print('Updating apt packages...')
    update_apt_packages()
    print('Setting up virtualenv...')
    create_venv()
    print('Initial setup complete.\n\nPlease reboot the system.\n')


def install_bash_aliases():
    """Install the .bash_aliases file in the home dir."""
    fname = 'bash_aliases'
    try:
        (HOME / f'.{fname}').symlink_to(SIMOC_SAM_DIR / fname)
    except FileExistsError:
        print(f'<~/.{fname}> already exists!')

def remove_home_dirs():
    """Remove unused default directories from the user's home."""
    dirs = ['Bookshelf', 'Desktop', 'Documents', 'Downloads',
            'Music', 'Pictures', 'Public', 'Templates', 'Videos']
    for dir_name in dirs:
        try:
            (HOME / dir_name).rmdir()
        except (FileNotFoundError, OSError):
            pass  # skip missing dirs or dirs that are not empty

def update_apt_packages():
    """Remove, update, upgrade, and install apt packages."""
    if APT_REMOVE:
        run(['sudo', 'apt', 'remove', '-y'] + APT_REMOVE, check=True)
    run(['sudo', 'apt', 'update'], check=True)
    run(['sudo', 'apt', 'upgrade', '-y'], check=True)
    if APT_INSTALL:
        run(['sudo', 'apt', 'install', '-y'] + APT_INSTALL, check=True)
    run(['sudo', 'apt', 'autoremove', '-y'], check=True)
    run(['sudo', 'apt', 'autoclean'], check=True)

def raspi_config(cmd, *args):
    """Run raspi-config with the specified command and arguments."""
    return subprocess.run(['sudo', 'raspi-config', 'nonint', cmd, *args],
                          check=True)

@cmd
def setup_locale(locale='en_US.UTF-8'):
    """Set up the system locale."""
    return raspi_config('do_change_locale', locale)

@cmd
def enable_i2c():
    """Enable i2c using raspi-config."""
    raspi_config('do_i2c', '0')

@needs_venv
def init_rtc():
    """Initialize and return the PCF8523 RTC sensor."""
    try:
        from simoc_sam.sensors.pcf8523 import PCF8523
    except ImportError as e:
        print(f'Error: Failed to import PCF8523 module: {e}')
        return
    try:
        return PCF8523(verbose=True)
    except Exception as e:
        print(f'Error: Failed to initialize PCF8523 RTC: {e}')

def parse_timestamp(timestamp):
    """Parse a timestamp string (ISO format or Unix timestamp)."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        try:
            return datetime.fromtimestamp(float(timestamp))
        except (ValueError, OSError) as e:
            print(f'Error: Invalid timestamp format: {e}')
            print('Use ISO format (YYYY-MM-DD HH:MM:SS) or Unix timestamp.')
            return

def print_times(rtc, label='Current'):
    """Print current system time and RTC time."""
    from datetime import datetime
    rpi_time = datetime.now()
    rtc_time = rtc.get_datetime()
    print(f'{label} RPi time: {rpi_time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{label} RTC time: {rtc_time.strftime("%Y-%m-%d %H:%M:%S")}')

def update_time(ts, target):
    """Update the time of the target (RPi or RTC) to the given timestamp."""
    from datetime import datetime
    rtc = init_rtc()
    if not rtc:
        return False
    dt = parse_timestamp(ts) if ts else None
    print_times(rtc, 'Current')
    try:
        if target == 'rpi':
            new_time = (dt or rtc.get_datetime()).strftime("%Y-%m-%d %H:%M:%S")
            print(f'Setting RPi time to: {new_time}')
            subprocess.run(['date', '-s', new_time], check=True)
        elif target == 'rtc':
            new_time = dt or datetime.now()
            print(f'Setting RTC time to: {new_time.strftime("%Y-%m-%d %H:%M:%S")}')
            rtc.set_datetime(new_time)
        print_times(rtc, 'Updated')
        print('Time updated successfully.')
        return True
    except Exception as e:
        print(f'Error: Failed to set time: {e}')
        return False

@cmd
@needs_root
def set_rpi_time(timestamp=None):
    """Set RPi system time from RTC or from a provided timestamp."""
    return update_time(timestamp, target='rpi')

@cmd
@needs_root
def set_rtc_time(timestamp=None):
    """Set RTC time from RPi system time or from a provided timestamp."""
    return update_time(timestamp, target='rtc')

@cmd
@needs_root
def setup_rtc():
    """Setup systemd service and timer for RTC time synchronization."""
    # Setup the boot service (RTC -> RPi) -- enable but don't start (boot-triggered)
    setup_systemd_unit('rtc-update-rpi', unit_type='service', enable=True, start=False)
    # Setup the periodic service (RPi -> RTC) -- don't enable/start (timer-triggered)
    setup_systemd_unit('rtc-update-pcf8523', unit_type='service', enable=False, start=False)
    # Setup the timer (triggers periodic RTC update) -- enable and start
    setup_systemd_unit('rtc-update-pcf8523', unit_type='timer', enable=True, start=True)
    print('RTC synchronization enabled.')

@cmd
@needs_root
def teardown_rtc():
    """Revert the changes made by the setup-rtc command."""
    # Stop and disable the timer
    teardown_systemd_unit('rtc-update-pcf8523', unit_type='timer', stop=True, disable=True)
    # Remove periodic service symlink (no need to stop/disable -- it's timer-triggered)
    teardown_systemd_unit('rtc-update-pcf8523', unit_type='service', stop=False, disable=False)
    # Disable boot service (no need to stop -- it's not running)
    teardown_systemd_unit('rtc-update-rpi', unit_type='service', stop=False, disable=True)
    run(['systemctl', 'daemon-reload'])
    print('RTC synchronization disabled.')

@cmd
def create_config():
    """Create a user config file in ~/.config/simoc-sam/ and a symlink to it."""
    # create simoc-sam dir in ~/.config
    config_dir = HOME / '.config' / 'simoc-sam'
    config_dir.mkdir(parents=True, exist_ok=True)
    # copy the default config.py file in there
    source_config = pathlib.Path(config.__file__).parent / 'defaults.py'
    dest_config = config_dir / 'config.py'
    shutil.copy2(source_config, dest_config)
    print(f'User config file created in: {dest_config}')
    # create symlink in current directory
    symlink_path = SIMOC_SAM_DIR / 'config.py'
    if symlink_path.exists():
        print(f'{symlink_path} already exists.')
        return
    try:
        symlink_path.symlink_to(dest_config)
        print(f'Symlink to user config file created in: {symlink_path}')
        print('You can now edit it to change the project configuration.')
    except OSError as e:
        print(f'Failed to create symlink: {e}')


@cmd
def clean_config():
    """Remove the user config symlink and user config file."""
    # remove symlink
    symlink_path = SIMOC_SAM_DIR / 'config.py'
    if symlink_path.is_symlink():
        symlink_path.unlink()
        print(f'Removed symlink: {symlink_path}')
    elif symlink_path.exists():
        print(f'{symlink_path} exists but is not a symlink. Skipping removal.')
    # remove the ~/.config/simoc-sam dir (since it only contains the user config file)
    config_dir = HOME / '.config' / 'simoc-sam'
    if config_dir.exists():
        shutil.rmtree(config_dir)
        print(f'Removed config directory: {config_dir}')


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
