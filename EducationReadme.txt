First start the SIO server. Right click on the folder and do "Open in Terminal".
1. Paste the command to start sioserver:
docker run --rm -it -p 8081:8080 -v `pwd`:/sioserver sioserver
2. Open a new terminal in the same directory.
If your SCD30 CO2 sensor is the only one connected (in order to view graphs properly):
python3 scd30.py -v --port 8081

You can also start the other sensors but it will break the CO2 graphs, but print the numbers on the page.
python3 sgp30.py -v --port 8081
python3 bme688.py -v --port 8081