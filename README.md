# SIMOC SAM
This repository contains a Docker container that include a sample
socketio server and client that will be the foundation of the socketio
server used in SAM.


## Using the `simoc-sam.py` script

The repo contains a `simoc-sam.py` script used to simplify several
operations.  The script will automatically create a venv (virtual
environment), install the dependencies, and run the commands inside
the venv.

You can see the full list of commands with `python simoc-sam.py -h`,
and you can run them with `python simoc-sam.py COMMAND`:
* `run-server` will start the `sioserver`
* `run-tmux` will launch the selected `tmux` script (`mqtt` or `sio`)
* `test` will execute the tests using `pytest`
* `info` will print host info about the network and sensors
* `hosts` will print information about the other hosts in the network


## Using the `venv` manually

If you want to manually run some of the scripts inside the `venv`,
you first have to activate the venv with `source venv/bin/activate`.
You can execute commands after activating the `venv` is activated, and
then leave the `venv` with `deactivate`.

Since the package is already installed within the `venv`, you can run
the scripts by doing `python -m simoc_sam.scriptname` (see the TL;DR
section for an example).


## Installation and dependencies

If you are using the `simoc-sam.py` script, you only need Python.

If you are using the Docker container (see below),  you need to have
Docker installed.

If you are running the Python client or server outside the container,
you need to install the `aiohttp` (only used by the server) and
`python-socketio` (used by both) packages using:
```sh
python3 -m pip install python-socketio aiohttp
```

Additionally, for the `tmux/` scripts you will need to install `tmux` with
`sudo apt install tmux`.


## Docker container usage
To build the Docker image using the `Dockerfile` included in the repo, run:

```sh
docker build . -t sioserver
```

You can then start the container with:
```sh
docker run --rm -it -p 8081:8080 sioserver
```

Once the container is running you can access the test client at
http://0.0.0.0:8081/


If you want to use a different port, use e.g. `-p 8082:8080` and
open http://0.0.0.0:8082/ instead.

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

To access the JS client simply open http://0.0.0.0:8081/ in the browser,
with the server running inside or outside the Docker container.

To run the Python client run `python3 sioclient.py`.  You can run
the server inside the container and the Python client inside or outside.

Regardless of the setup you choose, you must ensure that you are using the
correct port either in the URL (for the JS client) or as a command line
argument (for the Python client).  By default the server will serve on
port `8081`, unless you specified a different port with e.g. `-p 8082:8080`
while running the server inside the container.


## TL;DR
This is a summary of the commands you need to run everything.

### `venv`
Start everything with:
```sh
sudo apt install tmux
python3 simoc-sam.py run-tmux
```

Start the server with:
```sh
python3 simoc-sam.py run-server
```

Start the sensor(s)/client(s):
```sh
user@host:path$ source venv/bin/activate
(venv) user@host:path$ python -m simoc_sam.sensors.mocksensor -v
...
(venv) user@host:path$ deactivate
user@host:path$
```
You can run multiple sensors/clients on multiple terminal tabs
(you have to activate the `venv` in each of them).

### Docker
If you want to use Docker, do the initial setup (only needed once):
```sh
# build the image
docker build . -t sioserver
# install dependencies
python3 -m pip install python-socketio aiohttp
# install tmux (if using tmux/*.sh)
sudo apt install tmux
```

Start everything at once using `tmux`:
```sh
./tmux/mqtt.sh
```

Start server/sensor(s)/client(s) separately:
```sh
# start the Docker container and the socketio server
docker run --rm -it -p 8081:8080 -v `pwd`:/sioserver sioserver
# start the fake sensor (on a new terminal tab on the host machine)
python3 mocksensor.py -v
# start the client (on a new terminal tab on the host machine)
python3 sioclient.py
# start a live sensor (on a new terminal tab on the host machine)
python3 scd30.py -v

```

You will see the `mocksensor` producing data and the server receiving and
broadcasting them to all the connected clients.  You can open
http://0.0.0.0:8081/ to access the web client too.  You can also run
multiple sensors and clients at once.  If you restart the server, the
sensors and Python clients should reconnect automatically.


## Testing

Run the tests in the `venv` with:
```
python simoc-sam.py test
```

If you want to run them manually outside the `venv`, install
dependencies:
```
sudo pip install -U pytest pytest-asyncio
```

And then run the tests:
```
pytest -v
```
