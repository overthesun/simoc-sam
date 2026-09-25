## Cassandra driver
This is a base implementation of the DataStax Cassandra Python driver.

Make sure to install necessary libraries using:

```
pip install -r requirements.txt
```

The `.env` file contains necessary variables specific to your environment that will need to be set to allow the cluster to connect and create sessions.  

All current models are located in `cassandra_models.py` and should be changed here if adjustments are needed.

Parsing is currently tested and supported using `.cfg` and `.yaml` and more functionality will be built into as project expands. These files also contain examples of how to create database entries using the Cassandra Models and the `.create()` function

`cassandra_tables.py` and `cassandra_queries.py` use CQL statements and as of this time are an alternative to be used as opposed to the models from above.

`cass_db.py` show some example use cases of the functions created to drop and create tables, load from `.cfg` and `.yaml` files and load in data to the database. Due to the driver configuration there should not be a need to use these functions once the cluster is up and running and nodes are added. Using the `.create()` function using data from SIMOC-SAM should be all that is required to insert data into the database.


## Local Cassandra install(manual) on Raspberry Pis
1. Open terminal and go to script install location and run:
```
sudo chmod +x install.sh && ./install.sh
```
This will install the base installation of Cassandra


2. To make changes to the cluster to configure it to run off of IP address and setup your own cluster you will need to stop the service and configure the Cassandra files located in:
$CASSANDRA_HOME/conf
On 64bit OS:
`/etc/cassandra/conf`

If you are using the recommended 64bit OS stop the Cassandra service and clear the data:

```
sudo service cassandra stop
sudo rm -rf /var/lib/cassandra/*
```

Open the cassandra.yaml and set the following properties:
```
cluster_name
num_tokens
-seeds
listen_address
rpc_address
endpoint_snitch
```

num_tokens recommended value is 4

seeds can be multiple IP addresses separated by a comma i.e.
“1.1.1.1, 2.2.2.2”
*Never make all nodes seed nodes.

listen_address - IP of node

Rpc_address - IP of node (or 0.0.0.0 for wildcard but required broadcast address to not be blank)
endpoint_snitch set to GossipingPropertyFileSnitch for production configs

Save the file after the changes are made.

Open the cassandra-rackdc.properties file and set the following properties with your variables:
```
dc=
rack=
```
i.e. datacenter1, rac1/2/3/etc.

If using GossipingPropertyFileSnitch(recommended for production) remove cassandra-toplogy.properties from all other nodes on a new cluster.

After all changes are saved you can start the service again:
```sudo service cassandra start```  
Check if the node is up and running with:
```nodetool status```

*When starting the nodes again make sure the seed nodes are started one by one before the other nodes are started.
