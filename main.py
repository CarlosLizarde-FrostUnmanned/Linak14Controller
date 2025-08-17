#!/usr/bin/env python3
"""
LINAK 14 Linear Actuator Controller
A GUI application for controlling LINAK 14 linear actuators via CAN interface.
"""

import sys
import time
import threading
from typing import List, Optional, Dict
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import can
from dataclasses import dataclass
from enum import Enum


class LinakCommand(Enum):
    """LINAK actuator command types"""
    STOP = 0x03
    CLEAR_ERROR = 0x00
    ALL_OUT = 0x01
    ALL_IN = 0x02


@dataclass
class ActuatorConfig:
    """Configuration for a single actuator"""
    can_id: int
    name: str
    position: int = 0  # Current position in mm (0-130)


class LinakController:
    """Controller class for LINAK actuators via CAN"""

    def __init__(self, can_interface: str = 'kvaser', channel: str = '0', bitrate: int = 250000):
        self.can_interface = can_interface
        self.channel = channel
        self.bitrate = bitrate
        self.bus: Optional[can.BusABC] = None
        self.is_connected = False

    def connect(self) -> bool:
        """Connect to CAN bus"""
        try:
            self.bus = can.interface.Bus(
                interface=self.can_interface,
                channel=self.channel,
                bitrate=self.bitrate
            )
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

    def send_command(self, can_id: int, command: LinakCommand, position: Optional[int] = None) -> bool:
        """Send command to actuator"""
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
            self.bus.send(message)
            print(f"Sent command {command.name} to actuator {can_id}: {data}")
            return True

        except Exception as e:
            print(f"Failed to send command: {e}")
            return False

    def initialize_actuator(self, can_id: int) -> bool:
        """Initialize actuator by sending stop command"""
        return self.send_command(can_id, LinakCommand.STOP)

    def clear_error(self, can_id: int) -> bool:
        """Clear error register for actuator"""
        return self.send_command(can_id, LinakCommand.CLEAR_ERROR)


class ConfigDialog:
    """Configuration dialog for CAN interface and actuators"""

    def __init__(self, parent):
        self.parent = parent
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("LINAK Controller Configuration")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.setup_ui()

    def setup_ui(self):
        """Setup configuration dialog UI"""
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # CAN Interface Configuration
        can_frame = ttk.LabelFrame(main_frame, text="CAN Interface Configuration", padding="5")
        can_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(can_frame, text="Interface:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.interface_var = tk.StringVar(value="kvaser")
        interface_combo = ttk.Combobox(can_frame, textvariable=self.interface_var,
                                     values=["socketcan", "pcan", "vector", "kvaser"])
        interface_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))

        ttk.Label(can_frame, text="Channel:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.channel_var = tk.StringVar(value="0")
        channel_entry = ttk.Entry(can_frame, textvariable=self.channel_var, width=10)
        channel_entry.grid(row=0, column=3, sticky=(tk.W, tk.E))

        ttk.Label(can_frame, text="Bitrate:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        self.bitrate_var = tk.StringVar(value="250000")
        bitrate_combo = ttk.Combobox(can_frame, textvariable=self.bitrate_var,
                                   values=["125000", "250000", "500000", "1000000"])
        bitrate_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(5, 0))

        # Actuators Configuration
        actuators_frame = ttk.LabelFrame(main_frame, text="Actuators Configuration", padding="5")
        actuators_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        ttk.Label(actuators_frame, text="Number of Actuators:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.num_actuators_var = tk.StringVar(value="1")
        num_spin = ttk.Spinbox(actuators_frame, from_=1, to=8, textvariable=self.num_actuators_var,
                              width=5, command=self.update_actuator_list)
        num_spin.grid(row=0, column=1, sticky=tk.W, pady=(0, 10))

        # Actuators list
        list_frame = ttk.Frame(actuators_frame)
        list_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.actuators_tree = ttk.Treeview(list_frame, columns=("CAN ID", "Name"), show="tree headings", height=8)
        self.actuators_tree.heading("#0", text="Index")
        self.actuators_tree.heading("CAN ID", text="CAN ID")
        self.actuators_tree.heading("Name", text="Name")
        self.actuators_tree.column("#0", width=60)
        self.actuators_tree.column("CAN ID", width=80)
        self.actuators_tree.column("Name", width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.actuators_tree.yview)
        self.actuators_tree.configure(yscrollcommand=scrollbar.set)

        self.actuators_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Edit buttons
        button_frame = ttk.Frame(actuators_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))

        ttk.Button(button_frame, text="Edit Selected", command=self.edit_actuator).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_actuators).pack(side=tk.LEFT)

        # Dialog buttons
        dialog_buttons = ttk.Frame(main_frame)
        dialog_buttons.grid(row=2, column=0, columnspan=2, pady=(10, 0))

        ttk.Button(dialog_buttons, text="OK", command=self.ok_clicked).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(dialog_buttons, text="Cancel", command=self.cancel_clicked).pack(side=tk.RIGHT)

        # Initialize actuator list
        self.update_actuator_list()

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        actuators_frame.columnconfigure(1, weight=1)
        actuators_frame.rowconfigure(1, weight=1)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

    def update_actuator_list(self):
        """Update the actuators list based on number selected"""
        # Clear existing items
        for item in self.actuators_tree.get_children():
            self.actuators_tree.delete(item)

        # Add items based on number of actuators
        num_actuators = int(self.num_actuators_var.get())
        for i in range(num_actuators):
            can_id_dec = 418365689 + (256 * i)
            can_id = hex(can_id_dec)  # Default CAN IDs starting from 0xC0
            name = f"Actuator {i+1}"
            self.actuators_tree.insert("", tk.END, text=str(i+1), values=(f"{can_id}", name))

    def edit_actuator(self):
        """Edit selected actuator configuration"""
        selected = self.actuators_tree.selection()
        if not selected:
            messagebox.showwarning("Selection", "Please select an actuator to edit.")
            return

        item = selected[0]
        values = self.actuators_tree.item(item, "values")
        current_can_id = values[0]
        current_name = values[1]

        # Simple dialog for editing
        new_can_id = simpledialog.askstring("Edit CAN ID", f"Enter CAN ID (hex format, e.g., 0x18EFXXF9):",
                                           initialvalue=current_can_id)
        if new_can_id:
            new_name = simpledialog.askstring("Edit Name", "Enter actuator name:",
                                            initialvalue=current_name)
            if new_name:
                self.actuators_tree.item(item, values=(new_can_id, new_name))

    def reset_actuators(self):
        """Reset actuator configuration to defaults"""
        self.update_actuator_list()

    def ok_clicked(self):
        """Handle OK button click"""
        try:
            # Collect configuration
            config = {
                'interface': self.interface_var.get(),
                'channel': self.channel_var.get(),
                'bitrate': int(self.bitrate_var.get()),
                'actuators': []
            }

            # Collect actuator configurations
            for item in self.actuators_tree.get_children():
                values = self.actuators_tree.item(item, "values")
                can_id_str = values[0]
                name = values[1]

                # Parse CAN ID
                if can_id_str.startswith('0x'):
                    can_id = int(can_id_str, 16)
                else:
                    can_id = int(can_id_str)

                config['actuators'].append(ActuatorConfig(can_id=can_id, name=name))

            self.result = config
            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Configuration Error", f"Invalid configuration: {e}")

    def cancel_clicked(self):
        """Handle Cancel button click"""
        self.result = None
        self.dialog.destroy()


class ActuatorTile:
    """GUI tile for controlling a single actuator"""

    def __init__(self, parent_frame, actuator: ActuatorConfig, controller: LinakController):
        self.actuator = actuator
        self.controller = controller
        self.position_var = tk.DoubleVar(value=0.0)

        # Create tile frame
        self.frame = ttk.LabelFrame(parent_frame, text=actuator.name, padding="5")

        self.setup_ui()

    def setup_ui(self):
        """Setup actuator tile UI"""
        # Status indicator
        status_frame = ttk.Frame(self.frame)
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        self.status_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=(5, 0))

        # Position control
        pos_frame = ttk.Frame(self.frame)
        pos_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Label(pos_frame, text="Position (mm):").pack(side=tk.LEFT)
        self.position_scale = ttk.Scale(pos_frame, from_=0, to=130, orient=tk.HORIZONTAL,
                                       variable=self.position_var, length=150)
        self.position_scale.pack(side=tk.LEFT, padx=(5, 0))

        self.position_label = ttk.Label(pos_frame, text="0.0")
        self.position_label.pack(side=tk.LEFT, padx=(5, 0))

        # Update position label when scale changes
        self.position_var.trace('w', self.update_position_label)

        # Position entry
        entry_frame = ttk.Frame(self.frame)
        entry_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Label(entry_frame, text="Go to:").pack(side=tk.LEFT)
        self.position_entry = ttk.Entry(entry_frame, width=8)
        self.position_entry.pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(entry_frame, text="Go", command=self.go_to_position).pack(side=tk.LEFT, padx=(5, 0))

        # Control buttons
        button_frame = ttk.Frame(self.frame)
        button_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))

        ttk.Button(button_frame, text="All In", command=self.all_in).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(button_frame, text="All Out", command=self.all_out).pack(side=tk.LEFT, padx=(2, 2))
        ttk.Button(button_frame, text="Stop", command=self.stop).pack(side=tk.LEFT, padx=(2, 0))

        # Initialize/Clear buttons
        init_frame = ttk.Frame(self.frame)
        init_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))

        ttk.Button(init_frame, text="Initialize", command=self.initialize).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(init_frame, text="Clear Error", command=self.clear_error).pack(side=tk.LEFT, padx=(2, 0))

    def update_position_label(self, *args):
        """Update position label when scale changes"""
        pos = self.position_var.get()
        self.position_label.config(text=f"{pos:.1f}")

    def update_status(self, connected: bool):
        """Update connection status"""
        if connected:
            self.status_label.config(text="Connected", foreground="green")
        else:
            self.status_label.config(text="Disconnected", foreground="red")

    def go_to_position(self):
        """Go to specified position"""
        try:
            position = float(self.position_entry.get())
            position = max(0, min(130, position))  # Clamp to valid range

            # Clear error first
            self.controller.clear_error(self.actuator.can_id)
            time.sleep(0.1)  # Small delay

            # Send position command
            success = self.controller.send_command(self.actuator.can_id, None, position)
            if success:
                self.position_var.set(position)
                self.actuator.position = int(position)

        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for position (0-130 mm)")

    def all_in(self):
        """Move actuator all the way in"""
        self.controller.clear_error(self.actuator.can_id)
        time.sleep(0.1)
        self.controller.send_command(self.actuator.can_id, LinakCommand.ALL_IN)

    def all_out(self):
        """Move actuator all the way out"""
        self.controller.clear_error(self.actuator.can_id)
        time.sleep(0.1)
        self.controller.send_command(self.actuator.can_id, LinakCommand.ALL_OUT)

    def stop(self):
        """Stop actuator movement"""
        self.controller.send_command(self.actuator.can_id, LinakCommand.STOP)

    def initialize(self):
        """Initialize actuator"""
        success = self.controller.initialize_actuator(self.actuator.can_id)
        if success:
            messagebox.showinfo("Initialize", f"Actuator {self.actuator.name} initialized successfully")

    def clear_error(self):
        """Clear actuator error register"""
        success = self.controller.clear_error(self.actuator.can_id)
        if success:
            messagebox.showinfo("Clear Error", f"Error register cleared for {self.actuator.name}")


class LinakControllerApp:
    """Main application class"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LINAK 14 Actuator Controller")
        self.root.geometry("800x600")

        self.controller = LinakController()
        self.actuator_tiles: List[ActuatorTile] = []
        self.config = None

        self.setup_ui()

    def setup_ui(self):
        """Setup main application UI"""
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Configure", command=self.show_config_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Connection status frame
        status_frame = ttk.Frame(self.main_frame)
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(status_frame, text="CAN Status:").pack(side=tk.LEFT)
        self.can_status_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.can_status_label.pack(side=tk.LEFT, padx=(5, 20))

        self.connect_button = ttk.Button(status_frame, text="Connect", command=self.toggle_connection)
        self.connect_button.pack(side=tk.LEFT)

        # Emergency stop button
        self.emergency_stop_button = ttk.Button(status_frame, text="EMERGENCY STOP ALL",
                                               command=self.emergency_stop, state=tk.DISABLED)
        self.emergency_stop_button.pack(side=tk.RIGHT)

        # Actuators frame
        self.actuators_frame = ttk.LabelFrame(self.main_frame, text="Actuator Controls", padding="5")
        self.actuators_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Initial message
        self.no_config_label = ttk.Label(self.actuators_frame,
                                        text="Please configure the system using File -> Configure")
        self.no_config_label.pack(expand=True)

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

    def show_config_dialog(self):
        """Show configuration dialog"""
        dialog = ConfigDialog(self.root)
        self.root.wait_window(dialog.dialog)

        if dialog.result:
            self.config = dialog.result
            self.update_controller_config()
            self.create_actuator_tiles()

    def update_controller_config(self):
        """Update controller with new configuration"""
        if self.config:
            self.controller = LinakController(
                can_interface=self.config['interface'],
                channel=self.config['channel'],
                bitrate=self.config['bitrate']
            )

    def create_actuator_tiles(self):
        """Create actuator control tiles"""
        # Clear existing tiles
        for tile in self.actuator_tiles:
            tile.frame.destroy()
        self.actuator_tiles.clear()

        # Remove no config label
        self.no_config_label.pack_forget()

        # Create tiles in grid layout
        if self.config and self.config['actuators']:
            cols = min(3, len(self.config['actuators']))  # Max 3 columns
            rows = (len(self.config['actuators']) + cols - 1) // cols

            for i, actuator in enumerate(self.config['actuators']):
                row = i // cols
                col = i % cols

                tile = ActuatorTile(self.actuators_frame, actuator, self.controller)
                tile.frame.grid(row=row, column=col, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
                self.actuator_tiles.append(tile)

            # Configure grid weights for responsive layout
            for col in range(cols):
                self.actuators_frame.columnconfigure(col, weight=1)
            for row in range(rows):
                self.actuators_frame.rowconfigure(row, weight=1)

    def toggle_connection(self):
        """Toggle CAN connection"""
        if not self.config:
            messagebox.showerror("Configuration Error", "Please configure the system first.")
            return

        if self.controller.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """Connect to CAN bus"""
        if self.controller.connect():
            self.can_status_label.config(text="Connected", foreground="green")
            self.connect_button.config(text="Disconnect")
            self.emergency_stop_button.config(state=tk.NORMAL)

            # Update all tile statuses
            for tile in self.actuator_tiles:
                tile.update_status(True)

            # Initialize all actuators
            self.initialize_all_actuators()
        else:
            messagebox.showerror("Connection Error", "Failed to connect to CAN bus. Please check your configuration.")

    def disconnect(self):
        """Disconnect from CAN bus"""
        self.controller.disconnect()
        self.can_status_label.config(text="Disconnected", foreground="red")
        self.connect_button.config(text="Connect")
        self.emergency_stop_button.config(state=tk.DISABLED)

        # Update all tile statuses
        for tile in self.actuator_tiles:
            tile.update_status(False)

    def initialize_all_actuators(self):
        """Initialize all actuators with stop command"""
        for tile in self.actuator_tiles:
            self.controller.initialize_actuator(tile.actuator.can_id)
            time.sleep(0.05)  # Small delay between commands

    def emergency_stop(self):
        """Emergency stop all actuators"""
        for tile in self.actuator_tiles:
            self.controller.send_command(tile.actuator.can_id, LinakCommand.STOP)
        messagebox.showinfo("Emergency Stop", "All actuators have been stopped.")

    def run(self):
        """Run the application"""
        # Show initial configuration dialog
        self.show_config_dialog()

        # Start main loop
        self.root.mainloop()

        # Cleanup on exit
        if self.controller.is_connected:
            self.controller.disconnect()


def main():
    """Main entry point"""
    app = LinakControllerApp()
    app.run()


if __name__ == "__main__":
    main()
