# set vars
SNAME=SAM
SIOPORT=8081

tmux split-window -h -p 65
tmux send-keys -t $SNAME 'sleep 5' Enter "python3 simoc_live/simoc-web.py shell" Enter "npm run serve" Enter
