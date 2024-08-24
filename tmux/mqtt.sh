#!/bin/sh
# set vars
SNAME=${1:-SAM}  # use provided session name or SAM as default
SIOSERVER_ADDR=localhost:8081
# ensure we are in the right dir
cd ~/simoc-sam
# create a new session and set the num of cols/lines
tmux new-session -s $SNAME -d -x "$(tput cols)" -y "$(tput lines)"
# The first pane is just a shell
tmux send-keys -t $SNAME
# create 3 more panes for the sensors
tmux split-window -h -p 75
tmux send-keys -t $SNAME 'activate' Enter "python -m simoc_sam.sensors.scd30 -v --mqtt" Enter
tmux split-window -v -p 50
tmux send-keys -t $SNAME 'activate' Enter "python -m simoc_sam.sensors.bme688 -v --mqtt" Enter
# focus on the shell pane
tmux select-pane -t 0
# enable mouse input
tmux set -g mouse on
# set the title for the panes and show it on top
tmux set -g pane-border-status top
tmux set -g pane-border-format "#{pane_title}"
tmux select-pane -t 0 -T "Shell"
tmux select-pane -t 1 -T "SCD30"
tmux select-pane -t 2 -T "BME688"
# attach to the session
tmux attach-session -t $SNAME
