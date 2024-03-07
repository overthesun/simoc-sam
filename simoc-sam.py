"""Script to setup and run SIMOC-SAM."""

import re
import sys
import shutil
import socket
import pathlib
import argparse
import functools
import subprocess


SIMOC_SAM_DIR = pathlib.Path(__file__).resolve().parent
VENV_DIR = SIMOC_SAM_DIR / 'venv'
VENV_PY = str(VENV_DIR / 'bin' / 'python3')
DEPS = 'requirements.txt'
DEV_DEPS = 'dev-requirements.txt'
TMUX_SNAME = 'SAM'  # tmux session name

COMMANDS = {}

def cmd(func):
    """Decorator to add commands to the COMMANDS dict."""
    COMMANDS[func.__name__] = func
    return func

def run(args):
    print('>>', ' '.join(args))
    print('-'*80)
    result = subprocess.run(args)
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

target_re = re.compile('^(?:([^@]+)@)?([^:]+)(?::([^:]+))?$')
ipv4_re = re.compile('^\d+\.\d+\.\d+\.\d+$')  # does it look like an IPv4?
@cmd
def copy_repo(target, *, exclude_venv=True, exclude_git=True):
    """Copy the repository to a remote host using rsync."""
    user, host, path = target_re.fullmatch(target).groups()
    user = user or 'pi'
    path = path or '/home/pi/simoc-sam'
    repo = f'{pathlib.Path(__file__).parent}/'  # rsync wants the trailing /
    excludes = []
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


host_re = re.compile('^samrpi(\d+)$')
address_re = re.compile('^(\s*address\s+)((\d+\.\d+.\d+.)(\d+))(\s*)$')
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
