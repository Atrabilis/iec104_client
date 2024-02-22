# IEC104 Client

This Python library is designed to facilitate communication and interaction with systems using the IEC 60870-5-104 protocol, commonly used in electrical power systems for telecontrol, teleprotection, and associated telecommunications.

## Features

- **IEC104 Client Implementation**: Provides a Python-based client to interact with servers following the IEC 60870-5-104 standard.
- **Data Processing**: Includes utilities for processing data conforming to IEC 104 specifications.
- **Protocol Definitions**: Contains definitions and constants relevant to the IEC 104 protocol, aiding in the development and extension of the client.

## Installation

To use this library, clone the repository and include it in your Python project:

git clone https://github.com/Atrabilis/iec104_client.git

## Usage

Import the client in your Python script and initialize it with the appropriate settings for your IEC 104 server:

from iec104_client import IEC104Client

# Initialize the client with server IP and port
client = IEC104Client(server_ip='192.168.1.1', server_port=2404)

# Start communication
client.connect()

Refer to the `iec104_client.py`, `iec104_data_processor.py`, and `iec104_definitions.py` files for more detailed examples and usage.

## Contributing

Contributions to the `iec104_client` project are welcome. Please feel free to fork the repository, make your changes, and submit a pull request.

## License

This project is open-sourced under the [MIT License](LICENSE).

