from constants import *
from typing import Optional
import can
import sys
import os

class LinakController:
    """Controller class for LINAK actuators via CAN"""

    def __init__(self, can_interface: str = 'kvaser', channel: str = '0', bitrate: int = 250000):
        self.can_interface = can_interface
        self.channel = channel
        self.bitrate = bitrate
        self.bus: can.BusABC
        self.is_connected = False
        self.periodic_task = None #array
        self.waiting_limit_reached = False #array
        self.waiting_counter = 0 #array
        self.waiting_counter_limit = 5000
        self.listener = self.create_listener()

        self.notifier = Optional[can.Notifier]

        self.active_actuators_ids = []
        self.active_actuators_commands = []




    def connect(self) -> bool:
        """Connect to CAN bus"""
        try:
            self.bus = can.interface.Bus(
                interface=self.can_interface,
                channel=self.channel,
                bitrate=self.bitrate
            )

            self.notifier = can.Notifier(self.bus, listeners=[self.listener])

            self.is_connected = True
            print(f"Connected to CAN bus: {self.channel}")

            return True
        except Exception as e:
            print(f"Failed to connect to CAN bus: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Disconnect from CAN bus"""
        if self.bus:
            self.bus.shutdown()
            self.is_connected = False
            print("Disconnected from CAN bus")

    def send_command(self, actuator: ActuatorConfig, command: LinakCommand, position: Optional[int] = None) -> bool:
        """Send command to actuator"""
        can_id = actuator.can_id

        actuator.target_id_str = hex(can_id)[6] + hex(can_id)[7]
        print(f"Target ID: {actuator.target_id_str}")

        self.active_actuators_ids.append(actuator.target_id_str) if actuator.target_id_str not in self.active_actuators_ids else self.active_actuators_ids
        self.active_actuators_commands.append(command) if command not in self.active_actuators_commands else self.active_actuators_commands

        if not self.is_connected or not self.bus:
            return False

        try:
            if command == LinakCommand.STOP:
                data = [0x03, 0xFB, 0xFB, 0xFB, 0xFB, 0xFB, 0xFF, 0xFF]
            elif command == LinakCommand.CLEAR_ERROR:
                data = [0x00, 0xFB, 0xFB, 0xFB, 0xFB, 0xFB, 0xFF, 0xFF]
            elif command == LinakCommand.ALL_IN:
                data = [0x02, 0xFB, 0xFB, 0xFB, 0xFB, 0xFB, 0xFF, 0xFF]
            elif command == LinakCommand.ALL_OUT:
                data = [0x01, 0xFB, 0xFB, 0xFB, 0xFB, 0xFB, 0xFF, 0xFF]
            elif position is not None:
                # Convert position (0-130mm) to 0-64255 range
                pos_value = int((position / 130.0) * 64255)
                pos_value = max(0, min(64255, pos_value))  # Clamp to valid range
                pos_bytes = pos_value.to_bytes(2, byteorder='big')
                data = [pos_bytes[0], pos_bytes[1], 0xFB, 0xFB, 0xFB, 0xFB, 0xFF, 0xFF]
            else:
                return False

            message = can.Message(arbitration_id=can_id, data=data, is_extended_id=True)

            if command in [LinakCommand.ALL_IN, LinakCommand.ALL_OUT]:

                try:
                    self.periodic_task = self.bus.send_periodic(message, 0.025)
                except Exception as e:
                    print(f"Failed to send_periodic command: {e}")
                    return False

            if command != LinakCommand.ALL_IN and command != LinakCommand.ALL_OUT:
                self.bus.send(message)

            print(f"Sent command {command.name} to actuator {hex(can_id)}: {list(map(hex,data))}")
            return True

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            print(f"Failed to send command: {e}")
            return False

    def initialize_actuator(self, actuator: ActuatorConfig) -> bool:
        """Initialize actuator by sending stop command"""
        return self.send_command(actuator, LinakCommand.STOP)

    def clear_error(self, actuator: ActuatorConfig) -> bool:
        """Clear error register for actuator"""
        return self.send_command(actuator, LinakCommand.CLEAR_ERROR)

    def create_listener(self):
        return LinakController.CustomListener(self)

    class CustomListener(can.Listener, object):

        def __init__(self, parent_object):
            self.parent = parent_object

        # def on_message_received(self, msg: can.Message) -> None:
        #     print(f"Hola: {msg}{self.parent.test()}")
        #     pass

        def on_message_received(self, msg: can.Message) -> None:
            print(f"Response from {hex(msg.arbitration_id)}: {msg.data}")

        # while not reached and counter < counter_limit:
            self.parent.waiting_counter += 1
            # msg = self.parent.bus.recv(timeout=0.050)  # Add timeout to avoid blocking
            print(f"Counter = {self.parent.waiting_counter}")

            # print(f"Received message: {msg.data[1]}")

            source_id_str = hex(msg.arbitration_id)[8] + hex(msg.arbitration_id)[9]
            print(f"Source ID: {source_id_str}")

            for targetID in self.parent.active_actuators_ids:
                print(f"Target ID: {targetID}")

                if source_id_str == targetID:
                    print(f"Posicion: {msg.data[1]} {msg.data[0]}")

                    if LinakCommand.ALL_IN in self.parent.active_actuators_commands:
                        if msg.data[0] < 0x05 and msg.data[1] == 0x00:
                            print(f"ALL_IN Reached")
                            self.parent.waiting_limit_reached = True
                    if LinakCommand.ALL_OUT in self.parent.active_actuators_commands:
                        if msg.data[0] > 0x10 and msg.data[1] == 0x05:
                            print(f"ALL_OUT Reached")
                            self.parent.waiting_limit_reached = True

                if self.parent.waiting_limit_reached:
                    self.parent.periodic_task.stop()
                    self.parent.waiting_limit_reached = False
                    self.parent.waiting_counter = 0
                    self.parent.active_actuators_ids.remove(targetID)

                if self.parent.waiting_counter > self.parent.waiting_counter_limit:
                    self.parent.periodic_task.stop()
                    self.parent.waiting_limit_reached = False
                    self.parent.waiting_counter = 0
                    self.parent.active_actuators_ids.remove(targetID)
                    print("Error: TImeout waiting for a response")