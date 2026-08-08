import os

from dotenv import load_dotenv
from logging_config import log
from cassandra.cluster import Cluster
from cassandra.policies import RoundRobinPolicy, ConsistencyLevel

load_dotenv()

NODE = os.getenv('CASSANDRA_NODE')
KEYSPACE = os.getenv('CASSANDRA_KEYSPACE')
PORT = os.getenv('CASSANDRA_PORT')


def cassandra_connection():
    """
    Connection object for Cassandra
    Cluster can have multiple options configured for connection including auth if needed
    https://docs.datastax.com/en/developer/python-driver/3.25/getting_started/
    """
    cluster = Cluster([NODE],
                      port=PORT,
                      load_balancing_policy=RoundRobinPolicy(),
                      )
    session = cluster.connect()
    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS %s
        WITH REPLICATION =
        { 'class' : 'NetworkTopologyStrategy', 'replication_factor' : 3 }
        """ % KEYSPACE)

    log.info('setting keyspace')
    session.set_keyspace(KEYSPACE)
    return session, cluster


if __name__ == "__main__":
    log.info('Cannot call')
