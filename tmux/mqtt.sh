#!/bin/sh

# Start a tmux session with a Mock sensor generating data, a SIO bridge
# that receives the MQTT data and converts them for Socket IO, and an
# SIO client that receives and prints them.
# Requires tmux and an MQTT broker (mosquitto).
# Launch with `sam run-tmux mqtt`.

# set vars
SNAME=${1:-SAM}  # use provided session name or SAM as default
export SIOSERVER_ADDR=localhost:8081
export MQTTSERVER_ADDR=localhost:1883
# create a new session and set the num of cols/lines
tmux new-session -s $SNAME -d -x "$(tput cols)" -y "$(tput lines)"
# The first pane on the left runs the siobridge
tmux send-keys -t $SNAME 'activate' Enter "python -m simoc_sam.siobridge" Enter
# create 2 more panes for the Mock sensor and the sioclient
tmux split-window -h -p 65
tmux send-keys -t $SNAME 'activate && sleep 3' Enter "python -m simoc_sam.sensors.mocksensor -v --mqtt" Enter
tmux split-window -v -p 50
tmux send-keys -t $SNAME 'activate && sleep 5' Enter "python -m simoc_sam.sioclient" Enter
# focus on the left pane
tmux select-pane -t 0
# enable mouse input
tmux set -g mouse on
# set the title for the panes and show it on top
tmux set -g pane-border-status top
tmux set -g pane-border-format "#{pane_title}"
tmux select-pane -t 0 -T "SIO Bridge"
tmux select-pane -t 1 -T "Mock Sensor"
tmux select-pane -t 2 -T "SIO Client"
# attach to the session
tmux attach-session -t $SNAME
