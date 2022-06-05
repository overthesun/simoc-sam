#!/bin/sh

# set vars
SNAME=SAM
SIOPORT=8081
# create a new session and set the num of cols/lines
tmux new-session -s $SNAME -d -x "$(tput cols)" -y "$(tput lines)"
# start the server in the first pane
tmux send-keys -t $SNAME "docker run --rm -it -p $SIOPORT:8080 -v `pwd`:/simoc-sam/sioserver/sensors sioserver" Enter
tmux select-pane -t 0 -T "SIO Server"

# attach to the session
tmux attach-session -t $SNAME

