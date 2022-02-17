FROM ubuntu:21.10

MAINTAINER Ezio Melotti "ezio.melotti@gmail.com"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-pip \
    python3-setuptools \
    curl \
    wget

# Additional dependencies, conditionally installed, for ARMhf (especially Raspberry Pi)
Run if [ $(dpkg --print-architecture) = 'armhf' ]; then \
        echo "Installing additonal dependencies for ARMhf Architecture"; \
        apt-get install -y --no-install-recommends --upgrade \
        gcc-arm-linux-gnueabihf \
        python3-dev; \
    else \
        echo "Architecture is not ARMhf, so additional dependencies not needed."; \
    fi

# if we need more modules use a requirements.txt file
RUN python3 -m pip install python-socketio aiohttp

COPY . /sioserver

EXPOSE 8080

WORKDIR /sioserver

ENTRYPOINT [ "/bin/python3" ]
CMD ["sioserver.py"]
