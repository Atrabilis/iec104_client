# IEC104 Client

This Python library is designed to facilitate communication and interaction with systems using the IEC 60870-5-104 protocol, commonly used in electrical power systems for telecontrol, teleprotection, and associated telecommunications.

## Features

- **IEC104 Client Implementation**: Provides a Python-based client to interact with servers following the IEC 60870-5-104 standard.
- **Data Processing**: Includes utilities for processing data conforming to IEC 104 specifications.
- **Protocol Definitions**: Contains definitions and constants relevant to the IEC 104 protocol, aiding in the development and extension of the client.

## Installation

To use this library, clone the repository and include it in your Python project:
```bash
git clone https://github.com/Atrabilis/iec104_client.git
```
## Usage

Import the client in your Python script and initialize it with the appropriate settings for your IEC 104 server:
```python
from iec104_client import IEC104Client

# Initialize the client with server IP and port
client = IEC104Client(server_ip='192.168.1.1', server_port=2404)

# Start communication
client.start()

# Read data from the data queue
data = client.get_frame()
```
Refer to the `iec104_client.py`, `iec104_data_processor.py`, and `iec104_definitions.py` files for more details on the implementation.

## Elaborate example for a typical industrial environment:

```python
import time
from iec104_client import IEC104_Client
from iec104_data_processor import IEC104DataProcessor as dp
import logging
import os
import json
import db_utils

config_directory = os.path.join(
    os.path.dirname(__file__), "..", "config.json")

with open(config_directory, "r") as config_file:
    config_data = json.load(config_file)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[logging.FileHandler(config_data["rtu"]["log_path"]),
                              logging.StreamHandler()])

if __name__ == "__main__":
    azure_conn, azure_cursor = db_utils.connect_to_azure('{ODBC Driver 18 for SQL Server}',
                                                         config_data["azure"]["server"],
                                                         config_data["azure"]["database"],
                                                         config_data["azure"]["user"],
                                                         config_data["azure"]["password"])
    local_conn, local_cursor = db_utils.connect_and_initialize_db(config_data["database"]["host"],
                                                                  config_data["database"]["user"],
                                                                  config_data["database"]["password"],
                                                                  config_data["database"]["db_name"])
    client = IEC104_Client(
        config_data["rtu"]["ip"], config_data["rtu"]["port"], cheat_mode=True)

    batch_data = []  # Initialize the data batch
    batch_size = 100  # Define batch size, adjust as needed
    last_batch_time = time.time()
    batch_interval = 60  # Time interval in seconds to send the batch

    try:
        client.start()
        while not client.is_stopped():
            frame = client.get_frame()
            if frame:
                data = dp.decode_apdu(frame)

                if data["type_id"] == 36:  # Assuming only interested in type 36 data
                    for obj in data["objects"]:
                        # Prepare data for insertion
                        batch_data.append(
                            (obj["CP56Time2a"], obj["ioa"], obj["IEEE STD 754"]))

                        # Check if it's time to send the batch
                        if len(batch_data) >= batch_size or (time.time() - last_batch_time) >= batch_interval:
                            # Insert batch into databases
                            db_utils.batch_insert_into_rtu(
                                local_conn, batch_data)
                            db_utils.batch_insert_data_azure(
                                azure_conn, batch_data)

                            # Reset batch and time counter
                            batch_data = []
                            last_batch_time = time.time()

            else:
                time.sleep(60)  # Wait a bit if no frames

    except KeyboardInterrupt:
        print("Stopping the script due to user interruption (Ctrl+C).")
        client.stop()
    except Exception as e:
        print(f"Unexpected error: {e}. Stopping the script.")
        if client.is_stopped():
            print("IEC104 client has stopped.")
        client.stop()
    finally:
        if batch_data:
            db_utils.batch_insert_into_rtu(local_conn, batch_data)
            db_utils.batch_insert_data_azure(azure_conn, batch_data)
        print("The script has stopped.")

```


## To-Do List 

1. **Comprehensive Protocol Implementation**:
   - Ensure full implementation of the Application Protocol Control Information (APCI) and Application Service Data Unit (ASDU) structures as defined in the IEC 104 standard.
   - Implement all frame formats (I-format, S-format, U-format) with their respective functionalities.

2. **Data Processing Enhancements**:
   - Enhance data processing capabilities to handle a wider range of information objects and elements, including quality descriptors and time stamps.
   - Implement parsing and generation of ASDUs with variable structure qualifiers for efficient data transmission.

3. **Security Features**:
   - Integrate security features in line with IEC TS 60870-5-7 for secure authentication and encryption of communication channels.
   - Develop mechanisms for monitoring and logging to detect and respond to potential security threats.

4. **Error Handling and Recovery**:
   - Develop robust error handling and recovery mechanisms to manage communication timeouts, sequence number mismatches, and connection losses.

5. **Conformance and Interoperability Testing**:
   - Set up a testing framework for conformance testing based on IEC TS 60870-5-604 standards to ensure interoperability with other IEC 104 implementations.

6. **Documentation and Examples**:
   - Expand the documentation to include detailed examples of usage, configuration options, and troubleshooting tips.
   - Provide real-world use case implementations to demonstrate the library's capabilities in various scenarios.

7. **Performance Optimization**:
   - Analyze and optimize the performance for high-throughput and low-latency communication, especially for real-time control systems.

8. **Community and Contribution Guidelines**:
   - Establish clear guidelines for community contributions, including coding standards, pull request processes, and issue reporting templates.

9. **Extension and Customization**:
   - Allow for easy extension and customization of the library to support specific requirements of different electrical control and protection systems.

10. **Compliance with Latest Standards**:
    - Regularly update the library to comply with the latest revisions and extensions of the IEC 60870-5-104 standard.


## Contributing

Contributions to the `iec104_client` project are welcome. Please feel free to fork the repository, make your changes, and submit a pull request.

## License

This project is open-sourced under the [MIT License](LICENSE.md).

