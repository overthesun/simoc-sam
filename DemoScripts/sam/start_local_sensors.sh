#!/bin/sh

# set vars
SNAME=LOCAL
SIOPORT=8081
# create a new session and set the num of cols/lines
tmux new-session -s $SNAME -d -x "$(tput cols)" -y "$(tput lines)"
# start the server in the first pane
tmux send-keys -t $SNAME "python3 simoc-sam/vernier_CO2.py -v --port 8081" Enter
tmux select-pane -t 0 -T "LOCAL SENSOR"

# attach to the session
tmux attach-session -t $SNAME



