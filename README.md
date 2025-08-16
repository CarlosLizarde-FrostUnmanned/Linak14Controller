# LINAK 14 Linear Actuator Controller

A Python GUI application for controlling LINAK 14 linear actuators via CAN interface using the J1939 protocol.

## Features

- **Configurable CAN Interface**: Support for multiple CAN interfaces (socketcan, pcan, vector, kvaser)
- **Multi-Actuator Support**: Control up to 8 actuators simultaneously with individual CAN IDs
- **Intuitive GUI**: Tile-based interface with individual controls for each actuator
- **Safety Features**: Emergency stop functionality and proper initialization sequence
- **Real-time Control**: Position control with range 0-130mm (0-64255 internal units)

## Requirements

- Python 3.7+
- CAN interface hardware (USB-to-CAN adapter, etc.)
- LINAK 14 linear actuators

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd Linak14Controller
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install CAN interface drivers (varies by hardware):
   - For SocketCAN (Linux): Usually built-in
   - For PCAN: Install PEAK drivers
   - For Vector: Install Vector drivers
   - For Kvaser: Install Kvaser drivers

## Usage

1. **Run the application**:
```bash
python main.py
```

2. **Configure the system**:
   - Click "File" → "Configure" to open the configuration dialog
   - Set your CAN interface parameters:
     - Interface type (socketcan, pcan, vector, kvaser)
     - Channel (e.g., "can0", "PCAN_USBBUS1")
     - Bitrate (default: 250000 for J1939)
   - Configure actuators:
     - Set number of actuators (1-8)
     - Assign CAN IDs and names for each actuator
     - Default CAN IDs start from 0x100

3. **Connect and Control**:
   - Click "Connect" to establish CAN communication
   - Each actuator gets its own control tile with:
     - Position slider (0-130mm)
     - Direct position input
     - All In/All Out buttons
     - Stop button
     - Initialize and Clear Error functions

## LINAK 14 Protocol

The application implements the LINAK 14 command protocol:

### Initialization Sequence
1. **Stop Command** (sent on startup): `03 FB FB FB FB FB FF FF`
2. **Clear Error** (before each command): `00 FB FB FB FB FB FF FF`

### Available Commands
- **All In**: `02 FB FB FB FB FB FF FF`
- **All Out**: `01 FB FB FB FB FB FF FF`
- **Position Control**: `[HIGH_BYTE] [LOW_BYTE] FB FB FB FB FF FF` //TODO : Inverted bytes
  - Position range: 0-64255 (maps to 0-130mm)
  - 16-bit big-endian format

### Communication Settings
- **Protocol**: CAN J1939
- **Bitrate**: 250 kbps (standard)
- **Frame Type**: Standard (11-bit identifier) //TODO : 29-Bit

## Safety Features

- **Emergency Stop**: Immediately stops all actuators
- **Proper Initialization**: Ensures actuators are in safe state on startup
- **Error Handling**: Automatic error register clearing before commands
- **Range Limiting**: Position commands are clamped to valid range

## Troubleshooting

### CAN Connection Issues
1. Verify CAN interface is properly connected
2. Check driver installation for your CAN hardware
3. Ensure correct channel name and bitrate
4. On Linux, bring up CAN interface:
   ```bash
   sudo ip link set can0 up type can bitrate 250000
   ```

### Actuator Not Responding
1. Check CAN ID configuration
2. Verify actuator power and connections
3. Use "Initialize" button to reset actuator
4. Try "Clear Error" if actuator shows error state

### Permission Issues (Linux)
Add user to dialout group for USB CAN adapters:
```bash
sudo usermod -a -G dialout $USER
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.