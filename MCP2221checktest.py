import utils

if utils.check_for_MCP2221():
    print("MCP-2221 Detected! Running Sensor via USB!")
else:
    print("MCP-2221 Not Detected! Running Sensor via GPIO!")