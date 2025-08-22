#!/bin/sh

# Start a tmux session with 4 panes, one for each sensor (SCD30, BME688, SGP30)
# and an empty terminal (for a 4th sensor, debugging, etc.)
# Requires tmux and an MQTT broker (mosquitto).
# Launch with `sam run-tmux sensors`.

# set vars
SNAME=${1:-SAM}  # use provided session name or SAM as default
export MQTTSERVER_ADDR=localhost:1883
# create a new session and set the num of cols/lines
tmux new-session -s $SNAME -d -x "$(tput cols)" -y "$(tput lines)"
# Create 4 panes for the 3 sensors + a terminal
tmux send-keys -t $SNAME 'activate' Enter "python -m simoc_sam.sensors.scd30 -v --mqtt" Enter
tmux split-window -v
tmux send-keys -t $SNAME 'activate' Enter "python -m simoc_sam.sensors.bme688 -v --mqtt" Enter
tmux split-window -v
tmux send-keys -t $SNAME 'activate' Enter "python -m simoc_sam.sensors.sgp30 -v --mqtt" Enter
tmux split-window -v
tmux send-keys -t $SNAME 'activate' Enter
# set the layout to 4 equal rows
tmux select-layout even-vertical
# enable mouse input
tmux set -g mouse on
# set the title for the panes and show it on top
tmux set -g pane-border-status top
tmux set -g pane-border-format "#{pane_title}"
tmux select-pane -t 0 -T "SCD30"
tmux select-pane -t 1 -T "BME688"
tmux select-pane -t 2 -T "SGP30"
tmux select-pane -t 3 -T "Terminal"
# attach to the session
tmux attach-session -t $SNAME
