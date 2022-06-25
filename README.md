# SIMOC SAM
This repository contains a Docker container that include a sample
socketio server and client that will be the foundation of the socketio
server used in SAM.


## Installation and dependencies

If you are running everything inside the container (see below),
you only need to have Docker installed.

If you are running the Python client or server outside the container,
you need to install the `aiohttp` (only used by the server) and
`python-socketio` (used by both) packages using:
```sh
python3 -m pip install python-socketio aiohttp
```

# To set up the Vernier Sensors to run, do the following commands:
pip3 install godirect
sudo apt update
sudo apt install libusb1.0.0 # <-- this doesn't seem to exist. Try sudo apt-get install libusb-1.0.0 if it fails
sudo apt install libudev-dev
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="08f7", MODE="0666"' >> vstlibusb.rules
echo 'SUBSYSTEM=="usb_device", ATTRS{idVendor}=="08f7", MODE="0666"' >> vstlibusb.rules
sudo cp vstlibusb.rules /etc/udev/rules.d/.


## Docker container usage
To build the Docker image using the `Dockerfile` included in the repo, run:

```sh
docker build . -t sioserver
```

You can then start the container with:
```sh
docker run --rm -it -p 8080:8080 sioserver
```

Once the container is running you can access the test client at
http://0.0.0.0:8080/


If you want to use a different port, use e.g. `-p 8081:8080` and
open http://0.0.0.0:8081/ instead.

When the image is built, both the server and the client (and all other files)
are copied in the `/sioserver` directory of the container.  This means that
changes you do to these files won't be reflected unless you rebuild the image.

To avoid that, you can override the content of the `/sioserver` by using:
```sh
docker run --rm -it -p 8081:8080 -v `pwd`:/sioserver sioserver
```
After this you can edit the client and just reload the page to see the changes.
If you modify the server you will have to restart it.


## Connecting to the server
The repository includes two socketio clients:
* A JS one in `index.html`
* A standalone Python one (`sioclient.py`)

To access the JS client simply open http://0.0.0.0:8080/ in the browser,
with the server running inside or outside the Docker container.

To run the Python client run `python3 sioclient.py <port>`.  You can run
the server inside the container and the Python client inside or outside.

Regardless of the setup you choose, you must ensure that you are using the
correct port either in the URL (for the JS client) or as a command line
argument (for the Python client).  By default the server will serve on
port `8080`, unless you specified a different port with e.g. `-p 8081:8080`
while running the server inside the container.


## TL;DR

This is a summary of the commands you need to run everything.

Initial setup (only needed once):
```sh
# build the image
docker build . -t sioserver
# install dependencies
python3 -m pip install python-socketio aiohttp
# install tmux (if using tmux.sh)
sudo apt install tmux
```

To use Raspberry Pi using the qwiic shim, make sure that the i2c is enabled with
the following directions:
1. Use `raspi-config`
2. Choose option 3, Interface Options
3. Go to I5 I2C Enable/disable loading of i2c
4. Would you like the ARM I2C interface to be enabled? Yes
5. Choose Finish

Start everything at once using `tmux`:
```sh
./tmux.sh
```

Start server/sensor(s)/client(s) separately:
```sh
# start the Docker container and the socketio server
docker run --rm -it -p 8081:8080 -v `pwd`:/sioserver sioserver
# start the fake sensor (on a new terminal tab on the host machine)
python3 mocksensor.py -v --port 8081
# start the client (on a new terminal tab on the host machine)
python3 sioclient.py 8081
# start a live sensor (on a new terminal tab on the host machine)
python3 scd30.py -v --port 8081
python3 bme688.py -v --port 8081
python3 sgp30.py -v --port 8081

```

You will see the `mocksensor` producing data and the server receiving and
broadcasting them to all the connected clients.  You can open
http://0.0.0.0:8081/ to access the web client too.  You can also run
multiple sensors and clients at once.  If you restart the server, the
sensors and Python clients should reconnect automatically.

The web client currently does not run on properly on 8081 because it is
still expecting to receive batches which no longer exist. However, if
simoc-web is running, then sioserver will send to simoc-web and in the
ctrl+s capstone versions the sensor data can be seen from live mode there.

To configure sioserver to receive from non-local sensors, run open_port.sh to
open the port and view this system's IP to send sensor data to from the
non-local sensor.

Also, edit sioserver.py to add the IP of the sensor to the cors_allowed_origins.

## Testing

Install dependencies:

```sh
sudo pip install -U pytest pytest-asyncio
pip3 install adafruit-circuitpython-sgp30
pip3 install adafruit-circuitpython-bme680
```

Run tests:

```sh
pytest -v
```
