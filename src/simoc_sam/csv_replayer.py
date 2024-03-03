import os
import csv
import time
import json
import paho.mqtt.client as mqtt
import asyncio
from simoc_sam.sensors import utils
import ephem
import datetime


HOST = 'samrpi1.local'
PORT = 1883
KEEPALIVE = 60  # in seconds
CSV_DIRECTORY = "/home/sam/data"
speed_of_light_kmps = 299792.458  # Speed of light in kilometers per second
au_to_km = 149597870.7  # Convert distance from AU to kilometers
 
# Function to publish data to MQTT
def publish_to_mqtt(topic, payload):
    client.publish(topic, payload)

#async def process_csv_file(file_path, play_data_delay=60):
#    while True:
#        await process_once_csv_file(file_path, play_data_delay)
#        await asyncio.sleep(play_data_delay/10)

# Function to process a CSV file and publish data to MQTT continuously
async def process_csv_file(file_path, play_data_delay=60):
    # Extract topic name from the file name
    filename = os.path.basename(file_path)
    topic = filename.replace("_", "/").replace("sam/", "samreplay/").replace(".csv","")
    print(f"Ready to publish to topic '{topic}'")
    
    with open(file_path, newline='') as csv_file:
        csv_reader = csv.reader(csv_file)
        header = next(csv_reader, None)  # Assuming the first row is the header

        for row in csv_reader:
            # Assuming timestamp is in the 2nd column
            timestamp_str = row[1]
            #print(f"timestamp_str '{timestamp_str}'")
            # Get the current time minus the delay
            current_time_minus_delay = time.time() - play_data_delay
            #print(f"current_time_minus_delay '{current_time_minus_delay}'")
            # Convert timestamp to a datetime object 
            timestamp = time.mktime(time.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f"))
            #print(f"timestamp '{timestamp}'")

            # Skip rows with timestamps older than current_time_minus_delay
            if timestamp < current_time_minus_delay:
                continue
            
            wait_time = timestamp + play_data_delay - time.time()
            print(f"wait time '{wait_time}'")
            await asyncio.sleep(max(0, wait_time))

            # Create data dictionary dynamically based on CSV structure
            data = dict(zip(header, row))

            # Publish data to MQTT
            await loop.run_in_executor(None, publish_to_mqtt, topic, json.dumps(data))

            print(f"Published to topic '{topic}': {data}")


# main
async def main(csv_directory=CSV_DIRECTORY):

    #Calculate time lag Earth - Mars
    m = ephem.Mars()
    m.compute(datetime.datetime.utcnow())
    lag_seconds = play_data_delay = m.earth_distance * au_to_km / speed_of_light_kmps 
    lag_minutes = lag_seconds / 60
    print(f"Mars to Earth time lag in minutes: '{lag_minutes}'")

    # Process all CSV files in the directory
    tasks = []
    for filename in os.listdir(csv_directory):
        if filename.endswith(".csv"):
            file_path = os.path.join(csv_directory, filename)
            print("starting process_csv_file on " + filename + " with delay: " + str(play_data_delay))
            tasks.append(process_csv_file(file_path, play_data_delay))

    await asyncio.gather(*tasks)

if __name__ == '__main__':
    parser = utils.get_addr_argparser()
    parser.add_argument('--csv-directory', default="/home/sam/data",
                        help='the directory to scan for csv formatted data')
    args = parser.parse_args()

    # Create an MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    # Connect to the MQTT broker
    client.connect(host=HOST, port=PORT, keepalive=KEEPALIVE)
    print("Connecting to MQTT broker")

    # Loop to handle MQTT communication
    client.loop_start()

    main(args.csv_directory)

    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        # Disconnect from the MQTT broker on keyboard interrupt
        client.disconnect()
        print("Disconnected from MQTT broker")
        loop.close()

