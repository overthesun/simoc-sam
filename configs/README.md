# The `configs` directory

This directory contains configuration files that can be copied/symlinked
in order to update the configuration of the Raspberry Pi.
This should be done through the `simoc-sam.py` script

Files in this directory:
* `simoc_live.tmpl`: Nginx configuration file that statically serves the
  frontend and redirect socketio traffic to the backend
* `sensor-runner@.service`: `systemd` unit template file used to run the
  sensor scripts on boot
* `mosquitto-local.conf`: Mosquitto MQTT broker configuration file for
  local message brokering. Enables sensors, displays, and other components
  to communicate via MQTT. Listens on localhost only (127.0.0.1:1883).
