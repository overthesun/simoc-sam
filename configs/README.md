# The `configs` directory

This directory contains configuration files that can be copied/symlinked
in order to update the configuration of the Raspberry Pi.
This should be done through the `simoc-sam.py` script

Files in this directory:
* `simoc_live.tmpl`: Nginx configuration file that statically serves the
  frontend and redirect socketio traffic to the backend
