#!/bin/sh

# set vars
SNAME=SSH
tmux new-session -s waitdelay -d -x "$(tput cols)" -y "$(tput lines)"
tmux new-session -s waitdelay2 -d -x "$(tput cols)" -y "$(tput lines)"
tmux send-keys -t waitdelay "sleep 5; tmux wait-for -S login-delay" Enter
tmux send-keys -t waitdelay2 "sleep 10; tmux wait-for -S sensor-delay" Enter
# create a new session and set the num of cols/lines
tmux new-session -s $SNAME -d -x "$(tput cols)" -y "$(tput lines)"
tmux send-keys -t $SNAME "ssh gretchenpi@192.168.1.104" Enter
tmux wait-for login-delay
tmux kill-session -t waitdelay

tmux send-keys -t $SNAME "raspi" Enter
tmux wait-for sensor-delay

tmux send-keys -t $SNAME "./runsensor.sh" Enter
tmux kill-session -t waitdelay2

tmux select-pane -t 0 -T "SSH to Pi"

# attach to the session
tmux attach-session -t $SNAME





