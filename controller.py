from constants import *
from typing import Optional, Callable, Dict
import can
import sys
import os
import threading

class LinakController:
    """Controller class for LINAK actuators via CAN"""

    def __init__(self, can_interface: str = 'kvaser', channel: str = '0', bitrate: int = 250000):
        self.can_interface = can_interface
        self.channel = channel
        self.bitrate = bitrate
        self.bus: Optional[can.BusABC] = None
        self.is_connected = False

        # actuator SA -> state tracking
        self.actuator_states: Dict[str, Dict] = {}

        self.listener = self.create_listener()
        self.notifier: Optional[can.Notifier] = None

        # Optional user hook
        self.status_callback: Optional[Callable[[str, dict], None]] = None

        # Periodic timeout check
        self._timeout_checker: Optional[threading.Timer] = None
        self._timeout_interval = 0.1  # 100ms

    # -----------------
    # Connection methods
    # -----------------
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
            self._start_timeout_checker()
            print(f"Connected to CAN bus: {self.channel}")
            return True
        except Exception as e:
            print(f"Failed to connect to CAN bus: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Disconnect from CAN bus"""
        self.disconnect_bus()

        if self.bus:
            self.bus.shutdown()
        if self.notifier:
            self.notifier.stop()
        self._stop_timeout_checker()
        self.is_connected = False
        print("Disconnected from CAN bus.")

    def disconnect_bus(self):
        """Safely disconnect CAN bus and stop all tasks"""
        print("Disconnecting CAN bus...")

        # Stop all periodic actuator tasks
        for actuator_id_str, state in self.actuator_states.items():
            task = state.get("periodic_task")
            if task:
                try:
                    task.stop()
                except Exception as e:
                    print(f"Failed to stop periodic task for {actuator_id_str}: {e}")
                state["periodic_task"] = None

        # Stop the notifier threads
        if hasattr(self, "notifier") and self.notifier:
            try:
                self.notifier.stop()
            except Exception as e:
                print(f"Failed to stop notifier: {e}")
            self.notifier = None

        # Shutdown the CAN bus
        if hasattr(self, "bus") and self.bus:
            try:
                self.bus.shutdown()
            except Exception as e:
                print(f"Failed to shutdown bus: {e}")
            self.bus = None

        self.is_connected = False
        print("Disconnected from CAN bus")


    # -----------------
    # Commands
    # -----------------
    def send_command(self, actuator: ActuatorConfig, command: LinakCommand, position: Optional[int] = None) -> bool:
        """Send command to actuator"""
        if not self.is_connected or not self.bus:
            return False

        can_id = actuator.can_id
        # DA = target actuator address (2nd last byte)
        actuator_id_str = f"{(can_id >> 8) & 0xFF:02X}"

        # Register actuator state if not already
        if actuator_id_str not in self.actuator_states:
            self.actuator_states[actuator_id_str] = {
                "command": None,
                "periodic_task": None,
                "waiting_counter": 0,
                "waiting_limit": 5000,
                "waiting_limit_reached": False,
            }

        state = self.actuator_states[actuator_id_str]
        state["command"] = command

        # Build data payload as before
        try:
            if command == LinakCommand.STOP:
                # Stop any ongoing periodic task
                state = self.actuator_states.get(actuator_id_str)
                if state and state.get("periodic_task"):
                    try:
                        state["periodic_task"].stop()
                    except Exception as e:
                        print(f"Failed to stop periodic task: {e}")
                    state["periodic_task"] = None

                data = [0x03, 0xFB, 0xFB, 0xFB, 0xFB, 0xFB, 0xFF, 0xFF]
            elif command == LinakCommand.CLEAR_ERROR:
                data = [0x00, 0xFB, 0xFB, 0xFB, 0xFB, 0xFB, 0xFF, 0xFF]
            elif command == LinakCommand.ALL_IN:
                data = [0x02, 0xFB, 0xFB, 0xFB, 0xFB, 0xFB, 0xFF, 0xFF]
            elif command == LinakCommand.ALL_OUT:
                data = [0x01, 0xFB, 0xFB, 0xFB, 0xFB, 0xFB, 0xFF, 0xFF]
            elif position is not None:
                POSITION_MAX_RAW = 0x0514
                pos_value = int((position / 130.0) * POSITION_MAX_RAW)
                pos_value = max(0, min(POSITION_MAX_RAW, pos_value))
                pos_bytes = pos_value.to_bytes(2, byteorder='big')
                data = [pos_bytes[0], pos_bytes[1], 0xFB, 0xFB, 0xFB, 0xFB, 0xFF, 0xFF]
            else:
                return False

            message = can.Message(arbitration_id=can_id, data=data, is_extended_id=True)

            if command in [LinakCommand.ALL_IN, LinakCommand.ALL_OUT]:
                try:
                    state["periodic_task"] = self.bus.send_periodic(message, 0.025)
                except Exception as e:
                    print(f"Failed to send_periodic command: {e}")
                    return False
            else:
                self.bus.send(message)

            print(f"Sent command {command.name} to actuator {hex(can_id)}: {list(map(hex, data))}")
            return True

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            print(f"Failed to send command: {e}")
            return False


    def initialize_actuator(self, actuator: ActuatorConfig) -> bool:
        return self.send_command(actuator, LinakCommand.STOP)

    def clear_error(self, actuator: ActuatorConfig) -> bool:
        return self.send_command(actuator, LinakCommand.CLEAR_ERROR)

    # -----------------
    # Listener
    # -----------------
    def create_listener(self):
        return LinakController.CustomListener(self)

    class CustomListener(can.Listener):
        def __init__(self, parent_object):
            self.parent = parent_object

        def on_message_received(self, msg: can.Message) -> None:
            # Find the actuator state corresponding to this message
            state = None
            actuator_id_str = None
            for aid_str, s in self.parent.actuator_states.items():
                # Match by last byte (SA) of response, since DA/SA may vary
                if (msg.arbitration_id & 0xFF) == int(aid_str, 16):
                    state = s
                    actuator_id_str = aid_str
                    break

            if state is None:
                print(f"Untracked response from {hex(msg.arbitration_id)}: {msg.data}")
                return

            state["waiting_counter"] += 1
            cmd = state["command"]

            # Position bytes (flipped)
            position_raw = msg.data[1] << 8 | msg.data[0]
            POSITION_MAX_RAW = 0x0514  # 130 mm
            position_mm = round((position_raw / POSITION_MAX_RAW) * 130, 1)

            # Determine if actuator has reached its limit
            reached = False
            if cmd == LinakCommand.ALL_IN and position_raw <= 5:
                reached = True
            elif cmd == LinakCommand.ALL_OUT and position_raw >= POSITION_MAX_RAW - 5:
                reached = True

            if reached:
                print(f"{cmd.name} reached for actuator {actuator_id_str}")
                if state.get("periodic_task"):
                    state["periodic_task"].stop()
                    state["periodic_task"] = None
                state["waiting_counter"] = 0

            elif state["waiting_counter"] > state["waiting_limit"]:
                print(f"Error: Timeout waiting for actuator {actuator_id_str}")
                if state.get("periodic_task"):
                    state["periodic_task"].stop()
                    state["periodic_task"] = None
                state["waiting_counter"] = 0

            # Call optional status callback
            if self.parent.status_callback:
                self.parent.status_callback(actuator_id_str, {
                    "position_mm": position_mm,
                    "command": cmd.name if cmd else None,
                    "reached": reached,
                    "timeout": state["waiting_counter"] > state["waiting_limit"],
                    "raw_data": list(msg.data)
                })


    # -----------------
    # Timeout checker
    # -----------------
    def _start_timeout_checker(self):
        self._timeout_checker = threading.Timer(self._timeout_interval, self._timeout_check)
        self._timeout_checker.daemon = True
        self._timeout_checker.start()

    def _stop_timeout_checker(self):
        if self._timeout_checker:
            self._timeout_checker.cancel()
            self._timeout_checker = None

    def _timeout_check(self):
        for sa, state in self.actuator_states.items():
            if state["command"] in [LinakCommand.ALL_IN, LinakCommand.ALL_OUT] and state["waiting_counter"] > state["waiting_limit"]:
                print(f"Timeout waiting for actuator {sa}")
                if state["periodic_task"]:
                    state["periodic_task"].stop()
                    state["periodic_task"] = None
                state["waiting_counter"] = 0
                state["waiting_limit_reached"] = True

                # Trigger callback on timeout
                if self.status_callback:
                    self.status_callback(sa, {
                        "position_mm": None,
                        "command": state["command"].name if state["command"] else None,
                        "reached": False,
                        "timeout": True,
                        "raw_data": None
                    })

        # Reschedule
        self._start_timeout_checker()
