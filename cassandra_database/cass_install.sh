#!/bin/sh

kernel="$(uname)"
arch="$(uname -m)"

PACKAGES="openjdk-11-jdk vim docker.io "

case $kernel in
	Linux)
		echo "OS: Linux\nArch: ${arch}\n"
		sudo apt update && sudo apt upgrade -y
		sudo apt install $PACKAGES -y
		pip install cassandra-driver
		
		if [ "${arch}" = "armv7l" ]; then
			mkdir ~/Cassandra
			echo "Downloading Cassandra tarball"
			curl -OL https://dlcdn.apache.org/cassandra/4.0.3/apache-cassandra-4.0.3-bin.tar.gz
			tar xzvf apache-cassandra-4.0.3-bin.tar.gz
			
			mv apache-cassandra-4.0.3 ~/Cassandra
			cd ~/Cassandra/apache-cassandra-4.0.3/ && bin/cassandra -f
				
		elif [ "${arch}" = "aarch64" ]; then
		
			echo "Adding Cassandra Debian packages"
			echo "deb [arch=arm64] https://downloads.apache.org/cassandra/debian 40x main" | sudo tee -a /etc/apt/sources.list.d/cassandra.sources.list
			curl https://downloads.apache.org/cassandra/KEYS | sudo apt-key add -
			sudo apt update
			sudo apt install cassandra
			
		elif [ "${arch}" = "x86_64" ]; then
		
			echo "Adding Cassandra Debian packages"
			echo "deb https://downloads.apache.org/cassandra/debian 40x main" | sudo tee -a /etc/apt/sources.list.d/cassandra.sources.list
			curl https://downloads.apache.org/cassandra/KEYS | sudo apt-key add -
			sudo apt update
			sudo apt install cassandra
			
		else
			echo "Arch not currently targeted"
			echo "Exiting..."
			exit 1
		fi
		;;	
esac
