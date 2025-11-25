"""
Configuration variables handling for SIMOC Live.

This file tries to import the default vars from defaults.py,
then looks for a user config file in ~/.config/simoc-sam/config.py
and loads user overrides.

defaults.py shouldn't be imported directly by other modules --
they should just do `import config` and use `config.var` to get
either the default value or the one specified by the user.
"""

from pathlib import Path


# load default vars
from .defaults import *

# load user overrides (if the user config exists)
def load_user_config(config_path):
    if not config_path.exists():
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("user_config", config_path)
    user_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(user_config)
    # override only existing vars
    globals().update({
        k: getattr(user_config, k)
        for k in dir(user_config)
        if not k.startswith("_") and k in globals()
    })

user_config_path = Path.home() / ".config/simoc-sam/config.py"
load_user_config(user_config_path)


# validate and update config vars

# ensure path variables are Path objects
_path_vars = ['mqtt_certs_dir', 'simoc_web_dist_dir', 'log_dir']
for var in _path_vars:
    if var not in globals():
        continue
    v = globals()[var]
    if not isinstance(v, Path):
        globals()[var] = Path(v)

# set location from hostname if not set
if location is None:
    import socket
    hostname = socket.gethostname()
    # Remove trailing digits from the hostname to get the location
    location = hostname.rstrip('0123456789')

# warn if mqtt_secure is True but the certs dir does not exist
if mqtt_secure and not mqtt_certs_dir.exists():
    print(f"Warning: MQTT secure is enabled but the certs dir "
          f"<{mqtt_certs_dir}> does not exist.")

if not enable_jsonl_logging and data_source == 'logs':
    print("Warning: JSONL logging is disabled but data_source is 'logs'.")
