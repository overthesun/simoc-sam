FROM ubuntu:21.10

MAINTAINER Ezio Melotti "ezio.melotti@gmail.com"

# This prevents docker build from hanging on the time zone question
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends --upgrade \
    python3-pip \
    build-essential \
    python3-setuptools \
    curl \
    wget \
    gcc-arm-linux-gnueabihf \ 
    python-dev \ 
    python3-dev

# if we need more modules use a requirements.txt file
RUN pip3 install --upgrade pip
RUN python3 -m pip install python-socketio aiohttp frozenlist multidict yarl --no-binary :all: 

ENV TZ=America/Phoenix

COPY . /sioserver

EXPOSE 8080

WORKDIR /sioserver

ENTRYPOINT [ "/bin/python3" ]
CMD ["sioserver.py"]
