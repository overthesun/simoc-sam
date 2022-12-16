#!/bin/sh
# set vars
SNAME=SAM
SIOSERVER_ADDR=localhost:8081
# activate venv
echo -n 'Activating venv...   '
. venv/bin/activate
echo '[done]'
# create a new session and set the num of cols/lines
tmux new-session -s $SNAME -d -x "$(tput cols)" -y "$(tput lines)"
# start the server in the first pane
# tmux send-keys -t $SNAME "docker run --rm -it -p $SIOPORT:8080 -v `pwd`:/sioserver sioserver" Enter
tmux send-keys -t $SNAME "python -m simoc_sam.sioserver" Enter
# create 4 more panes and run the sensors and clients
tmux split-window -h -p 65
tmux send-keys -t $SNAME 'sleep 5' Enter "python -m simoc_sam.sensors.adafruit -v" Enter
tmux split-window -v
tmux send-keys -t $SNAME 'sleep 12' Enter "python -m simoc_sam.sensors.vernier -v" Enter
tmux split-window -h -p 50
tmux send-keys -t $SNAME 'sleep 17' Enter "python -m simoc_sam.sioclient" Enter
tmux select-pane -t 1
tmux split-window -h -p 50
tmux send-keys -t $SNAME 'sleep 10' Enter "python -m simoc_sam.sensors.mocksensor -v" Enter
# focus on the server pane
tmux select-pane -t 0
# enable mouse input
tmux set -g mouse on
# set the title for the panes and show it on top
tmux set -g pane-border-status top
tmux set -g pane-border-format "#{pane_title}"
tmux select-pane -t 0 -T "Server"
tmux select-pane -t 1 -T "Adafruit"
tmux select-pane -t 2 -T "MockSensor"
tmux select-pane -t 3 -T "Vernier"
tmux select-pane -t 4 -T "Client 1"
# attach to the session
tmux attach-session -t $SNAME
# deactivate venv when leaving
echo -n 'Deactivating venv... '
deactivate
echo '[done]'
