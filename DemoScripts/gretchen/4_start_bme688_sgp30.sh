# set vars
SNAME=SAM
SIOPORT=8081

tmux split-window -h -p 65
tmux send-keys -t $SNAME 'sleep 5' Enter "python3 sensors/sgp30.py -v --port 8081" Enter

tmux split-window -h -p 65
tmux send-keys -t $SNAME 'sleep 5' Enter "python3 sensors/bme688.py -v --port 8081" Enter