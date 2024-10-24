#!/bin/bash

# This script checks if the RPi is online.
# If not, it restarts the network interface,
# checks again, and if it's still offline,
# it reboots the RPi

# Define the IP address or hostname to check connectivity
PING_TARGET="google.com"
RETRY_COUNT=5
INTERFACE="eth0"

while true; do
    echo "Checking ping results for eth0 restart"
    # Ping the target
    ping -c $RETRY_COUNT $PING_TARGET 
    # Check if the ping was unsuccessful
    if [ $? -ne 0 ]; then
        echo "Network down. Restarting $INTERFACE..."
        ip link set $INTERFACE down
        sleep 10
        ip link set $INTERFACE up
        sleep 5
        dhclient $INTERFACE 

        
        # Wait for some time to allow reconnection
        sleep 20
        
        echo "Checking ping results for reboot"
        # Ping again to see if the network is back up
        ping -c $RETRY_COUNT $PING_TARGET 
        if [ $? -ne 0 ]; then
            echo "Network still down. Rebooting..."
            reboot
        fi
    fi
    
    # Check the network status every 2 minutes
    sleep 240
done

