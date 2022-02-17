FROM ubuntu:21.10

MAINTAINER Ezio Melotti "ezio.melotti@gmail.com"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-pip \
    python3-setuptools \
    curl \
    wget && \
    if [ $(dpkg --print-architecture) = 'armhf' ]; then \
        apt-get install -y --no-install-recommends --upgrade \
        gcc-arm-linux-gnueabihf \
        python3-dev; \
    fi

# if we need more modules use a requirements.txt file
RUN python3 -m pip install python-socketio aiohttp

COPY . /sioserver

EXPOSE 8080

WORKDIR /sioserver

ENTRYPOINT [ "/bin/python3" ]
CMD ["sioserver.py"]
