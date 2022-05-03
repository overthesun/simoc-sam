
#!/bin/sh

# First run chmod 777 runVernier.sh so this script will run!
# Make script executable so we can find it with grep comand
chmod 777 vernier.py
attempts=20
SNAME=VernierRun

# Kill any sessions running from before
tmux kill-session -t waitdelay
tmux kill-session -t $SNAME
# create a new session
tmux new-session -s $SNAME -d -x "$(tput cols)" -y "$(tput lines)"
# Try to start the script
tmux send-keys -t $SNAME "./vernier.py $1 $2 $3 $4 $5" Enter


# Example loop
#i=0; while [ $i -le $attempts ]; do echo $i; i=$((i+1)); done

# Wait and see if script starts
tmux new-session -s waitdelay -d -x "$(tput cols)" -y "$(tput lines)"
tmux send-keys -t waitdelay "sleep 4; tmux wait-for -S time-delay" Enter
tmux wait-for time-delay
tmux kill-session -t waitdelay

# If it started, then more than 0 lines have vernier.py in processes.
procCount=$( ps -e | grep vernier.py | wc -l )
if [ $procCount -gt 0 ]; then
	echo "RUNNING!"
else
	echo "NOT RUNNING YET! WILL KEEP TRYING"
# keep trying till script starts
i=0; while [ $i -le $attempts ]; do echo $i; i=$((i+1));
	# Try to start the script
	tmux send-keys -t $SNAME "./vernier.py $1 $2 $3 $4 $5" Enter

	# Wait
	tmux new-session -s waitdelay -d -x "$(tput cols)" -y "$(tput lines)"
	tmux send-keys -t waitdelay "sleep 4; tmux wait-for -S time-delay" Enter
	tmux wait-for time-delay
	tmux kill-session -t waitdelay

	#Check
	procCount=$( ps -e | grep vernier.py | wc -l )
	if [ $procCount -gt 0 ]; then
       		 echo "Running now"
		 break
	else
          	echo "NOT RUNNING YET!"
	fi
	# End of if within loop
done
#end of if first try
fi

tmux select-pane -t 0 -T "VernierRun"


# attach to the session
tmux attach-session -t $SNAME


