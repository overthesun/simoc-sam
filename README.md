# SIMOC SAM
This repository contains a Docker container that include a sample
socketio server and client that will be the foundation of the socketio
server used in SAM.

## Docker container usage
To build the Docker image using the `Dockerfile` included in the repo, run:

```sh
docker build . -t sioserver
```

You can then start the container with:
```sh
docker run -it -p 8080:8080 sioserver
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
docker run -it -p 8081:8080 -v `pwd`:/sioserver sioserver
```
After this you can edit the client and just reload the page to see the changes.
If you modify the server you will have to restart it.
