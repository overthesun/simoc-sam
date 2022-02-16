architecture=`dpkg --print-architecture`

if [ $architecture = "armhf" ]; 
then
    echo "$architecture architecture detected, using armhf build (used with Rasperry Pi).";
    docker build - < DockerfileRpi -t sioserver;
elif [ $architecture = "amd64" ]; 
then
    echo "$architecture architecture detected. Using amd64 build.";
    docker build - < Dockerfile -t sioserver;
else
    echo "$architecture architecture detected. This is untested. Try manually running docker with one of the Dockerfiles using 'docker build - < Dockerfile -t sioserver' Dockerfile is for amd64 and DockerfileRpi is for armhf.";
fi
