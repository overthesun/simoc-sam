#!/bin/sh

# set vars
SNAME=FRONT

# create a new session and set the num of cols/lines
tmux new-session -s $SNAME -d -x "$(tput cols)" -y "$(tput lines)"
tmux send-keys -t $SNAME "python3 simoc-web/simoc-web.py shell" Enter "npm run serve" Enter
tmux select-pane -t 0 -T "Front End"

# attach to the session
tmux attach-session -t $SNAME
