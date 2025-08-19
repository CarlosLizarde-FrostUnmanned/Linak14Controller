from enum import Enum
from dataclasses import dataclass

class LinakCommand(Enum):
    """LINAK actuator command types"""
    STOP = 0x03
    CLEAR_ERROR = 0x00
    ALL_OUT = 0x01
    ALL_IN = 0x02
    GO_TO = 0x04

@dataclass
class ActuatorConfig:
    """Configuration for a single actuator"""
    can_id: int
    name: str
    position: int = 0  # Current position in mm (0-130)
    target_id_str = '' #Actuator Address ID in hex
    target_command = ''
