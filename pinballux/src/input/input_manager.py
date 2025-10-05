"""
Input management system for keyboard and joystick support
"""

import pygame
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from typing import Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass

from ..core.logger import get_logger

logger = get_logger(__name__)


class InputAction(Enum):
    """Input actions that can be triggered"""
    WHEEL_LEFT = "wheel_left"
    WHEEL_RIGHT = "wheel_right"
    SELECT = "select"
    EXIT = "exit"
    ROTATE = "rotate"  # R key for display rotation like PinballX
    PAUSE = "pause"
    FLIPPERS = "flippers"
    NUDGE_LEFT = "nudge_left"
    NUDGE_RIGHT = "nudge_right"
    NUDGE_UP = "nudge_up"
    PLUNGER = "plunger"
    START = "start"
    EXTRA_BALL = "extra_ball"
    MENU = "menu"


@dataclass
class InputBinding:
    """Represents a binding between input and action"""
    action: InputAction
    key_code: Optional[int] = None  # PyQt6 key code
    key_name: Optional[str] = None  # Key name (e.g., "Shift_L", "Shift_R") for modifiers
    joystick_button: Optional[int] = None  # Joystick button number
    joystick_axis: Optional[int] = None  # Joystick axis number
    joystick_axis_direction: Optional[str] = None  # 'positive' or 'negative'
    joystick_hat: Optional[int] = None  # Hat number
    joystick_hat_direction: Optional[str] = None  # 'up', 'down', 'left', 'right'


class InputManager(QObject):
    """Manages keyboard and joystick input"""

    # Signals for input actions
    action_triggered = pyqtSignal(InputAction)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.config = config

        # Input state
        self.joysticks = []
        self.input_bindings: List[InputBinding] = []
        self.joystick_enabled = True
        self.keyboard_enabled = True

        # Polling timer for joystick input
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self._poll_joysticks)
        self.poll_interval = 16  # ~60 FPS

        # Previous joystick state for change detection
        self.prev_joystick_state = {}

        self._initialize_pygame()
        self._setup_default_bindings()

    def _get_qt_key(self, key_name: str):
        """Convert key name string to Qt key code"""
        from PyQt6.QtCore import Qt

        # Map common key names to Qt key codes
        key_map = {
            # Standard keys
            'Escape': Qt.Key.Key_Escape,
            'Return': Qt.Key.Key_Return,
            'Enter': Qt.Key.Key_Enter,
            'Space': Qt.Key.Key_Space,
            'Tab': Qt.Key.Key_Tab,

            # Arrow keys
            'Left': Qt.Key.Key_Left,
            'Right': Qt.Key.Key_Right,
            'Up': Qt.Key.Key_Up,
            'Down': Qt.Key.Key_Down,

            # Shift keys
            'Shift_L': Qt.Key.Key_Shift,
            'Shift_R': Qt.Key.Key_Shift,
            'Shift': Qt.Key.Key_Shift,

            # Control keys
            'Control_L': Qt.Key.Key_Control,
            'Control_R': Qt.Key.Key_Control,
            'Control': Qt.Key.Key_Control,

            # Alt keys
            'Alt_L': Qt.Key.Key_Alt,
            'Alt_R': Qt.Key.Key_Alt,
            'Alt': Qt.Key.Key_Alt,

            # Letter keys
            **{chr(i): getattr(Qt.Key, f'Key_{chr(i).upper()}') for i in range(ord('a'), ord('z') + 1)},
            **{chr(i): getattr(Qt.Key, f'Key_{chr(i)}') for i in range(ord('A'), ord('Z') + 1)},

            # Number keys
            **{str(i): getattr(Qt.Key, f'Key_{i}') for i in range(10)},
        }

        qt_key = key_map.get(key_name)
        if qt_key is None:
            self.logger.warning(f"Unknown key name: {key_name}, using default")
        return qt_key

    def _initialize_pygame(self):
        """Initialize pygame for joystick support"""
        try:
            pygame.init()
            pygame.joystick.init()

            joystick_count = pygame.joystick.get_count()
            self.logger.info(f"Found {joystick_count} joystick(s)")

            # Initialize all joysticks
            for i in range(joystick_count):
                try:
                    joystick = pygame.joystick.Joystick(i)
                    joystick.init()
                    self.joysticks.append(joystick)

                    self.logger.info(f"Initialized joystick {i}: {joystick.get_name()}")
                    self.logger.info(f"  Buttons: {joystick.get_numbuttons()}")
                    self.logger.info(f"  Axes: {joystick.get_numaxes()}")
                    self.logger.info(f"  Hats: {joystick.get_numhats()}")

                    # Initialize previous state
                    self.prev_joystick_state[i] = {
                        'buttons': [False] * joystick.get_numbuttons(),
                        'axes': [0.0] * joystick.get_numaxes(),
                        'hats': [(0, 0)] * joystick.get_numhats()
                    }

                except Exception as e:
                    self.logger.error(f"Failed to initialize joystick {i}: {e}")

        except Exception as e:
            self.logger.error(f"Failed to initialize pygame: {e}")
            self.joystick_enabled = False

    def _setup_default_bindings(self):
        """Setup default input bindings"""
        from PyQt6.QtCore import Qt

        # Start with empty bindings
        self.input_bindings = []

        # Load keyboard bindings from config if available
        if self.config and hasattr(self.config, 'input'):
            self.logger.info("Loading keyboard bindings from config")

            # Map config key names to Qt key codes
            key_mapping = {
                self.config.input.left_key: (InputAction.WHEEL_LEFT, self._get_qt_key(self.config.input.left_key)),
                self.config.input.right_key: (InputAction.WHEEL_RIGHT, self._get_qt_key(self.config.input.right_key)),
                self.config.input.select_key: (InputAction.SELECT, self._get_qt_key(self.config.input.select_key)),
                self.config.input.exit_key: (InputAction.EXIT, self._get_qt_key(self.config.input.exit_key)),
            }

            for key_name, (action, qt_key) in key_mapping.items():
                if qt_key is not None:
                    # Store both key_code and key_name for proper matching
                    self.input_bindings.append(InputBinding(action, key_code=qt_key, key_name=key_name))
                    self.logger.debug(f"Mapped {key_name} -> {action}")

            # Always add R for rotate (not configurable)
            self.input_bindings.append(InputBinding(InputAction.ROTATE, key_code=Qt.Key.Key_R))
        else:
            # Default keyboard bindings if no config
            self.logger.info("Using default keyboard bindings")
            self.input_bindings = [
                # Navigation
                InputBinding(InputAction.WHEEL_LEFT, key_code=Qt.Key.Key_Left),
                InputBinding(InputAction.WHEEL_RIGHT, key_code=Qt.Key.Key_Right),
                InputBinding(InputAction.SELECT, key_code=Qt.Key.Key_Return),
                InputBinding(InputAction.SELECT, key_code=Qt.Key.Key_Enter),
                InputBinding(InputAction.EXIT, key_code=Qt.Key.Key_Escape),
                InputBinding(InputAction.ROTATE, key_code=Qt.Key.Key_R),  # R key for display rotation

                # Game controls
                InputBinding(InputAction.FLIPPERS, key_code=Qt.Key.Key_Space),
                InputBinding(InputAction.NUDGE_LEFT, key_code=Qt.Key.Key_A),
                InputBinding(InputAction.NUDGE_RIGHT, key_code=Qt.Key.Key_D),
                InputBinding(InputAction.NUDGE_UP, key_code=Qt.Key.Key_W),
                InputBinding(InputAction.PLUNGER, key_code=Qt.Key.Key_S),
                InputBinding(InputAction.START, key_code=Qt.Key.Key_1),
                InputBinding(InputAction.EXTRA_BALL, key_code=Qt.Key.Key_2),
                InputBinding(InputAction.PAUSE, key_code=Qt.Key.Key_P),
                InputBinding(InputAction.MENU, key_code=Qt.Key.Key_Tab),
            ]

        # Load joystick button mappings from config if available
        if self.config and hasattr(self.config, 'input') and self.config.input.joystick_buttons:
            self.logger.info("Loading joystick button mappings from config")
            for action_name, button_num in self.config.input.joystick_buttons.items():
                try:
                    action = InputAction(action_name.lower())
                    self.input_bindings.append(
                        InputBinding(action, joystick_button=button_num)
                    )
                    self.logger.debug(f"Mapped button {button_num} -> {action}")
                except ValueError:
                    self.logger.warning(f"Unknown action in config: {action_name}")
        else:
            # Default joystick bindings (if joystick available and no config)
            self.logger.info("Using default joystick bindings")
            self.input_bindings.extend([
                # Navigation with D-pad
                InputBinding(InputAction.WHEEL_LEFT, joystick_hat=0, joystick_hat_direction='left'),
                InputBinding(InputAction.WHEEL_RIGHT, joystick_hat=0, joystick_hat_direction='right'),

                # Navigation with analog stick
                InputBinding(InputAction.WHEEL_LEFT, joystick_axis=0, joystick_axis_direction='negative'),
                InputBinding(InputAction.WHEEL_RIGHT, joystick_axis=0, joystick_axis_direction='positive'),

                # Buttons
                InputBinding(InputAction.SELECT, joystick_button=0),  # Usually A/X button
                InputBinding(InputAction.FLIPPERS, joystick_button=4),  # Usually L1/LB
                InputBinding(InputAction.FLIPPERS, joystick_button=5),  # Usually R1/RB
                InputBinding(InputAction.PLUNGER, joystick_button=2),   # Usually Y/Triangle
                InputBinding(InputAction.START, joystick_button=9),     # Usually Start
                InputBinding(InputAction.MENU, joystick_button=8),      # Usually Select/Back
            ])

        self.logger.info(f"Configured {len(self.input_bindings)} input bindings")

    def start_polling(self):
        """Start polling for joystick input"""
        if self.joystick_enabled and self.joysticks:
            self.poll_timer.start(self.poll_interval)
            self.logger.info("Started joystick polling")

    def stop_polling(self):
        """Stop polling for joystick input"""
        self.poll_timer.stop()
        self.logger.info("Stopped joystick polling")

    def _poll_joysticks(self):
        """Poll joystick input and detect changes"""
        if not self.joystick_enabled:
            return

        try:
            pygame.event.pump()

            for joystick_id, joystick in enumerate(self.joysticks):
                if joystick_id not in self.prev_joystick_state:
                    continue

                prev_state = self.prev_joystick_state[joystick_id]

                # Check buttons
                for button_id in range(joystick.get_numbuttons()):
                    current_pressed = joystick.get_button(button_id)
                    prev_pressed = prev_state['buttons'][button_id]

                    # Trigger on button press (not release)
                    if current_pressed and not prev_pressed:
                        self._handle_joystick_button(joystick_id, button_id)

                    prev_state['buttons'][button_id] = current_pressed

                # Check axes
                for axis_id in range(joystick.get_numaxes()):
                    current_value = joystick.get_axis(axis_id)
                    prev_value = prev_state['axes'][axis_id]

                    # Check for axis threshold crossing
                    threshold = 0.5
                    if abs(current_value) > threshold and abs(prev_value) <= threshold:
                        direction = 'positive' if current_value > 0 else 'negative'
                        self._handle_joystick_axis(joystick_id, axis_id, direction)

                    prev_state['axes'][axis_id] = current_value

                # Check hats (D-pad)
                for hat_id in range(joystick.get_numhats()):
                    current_hat = joystick.get_hat(hat_id)
                    prev_hat = prev_state['hats'][hat_id]

                    if current_hat != prev_hat:
                        self._handle_joystick_hat(joystick_id, hat_id, current_hat)

                    prev_state['hats'][hat_id] = current_hat

        except Exception as e:
            self.logger.error(f"Error polling joysticks: {e}")

    def _handle_joystick_button(self, joystick_id: int, button_id: int):
        """Handle joystick button press"""
        for binding in self.input_bindings:
            if binding.joystick_button == button_id:
                self.logger.debug(f"Joystick {joystick_id} button {button_id} -> {binding.action}")
                self.action_triggered.emit(binding.action)

    def _handle_joystick_axis(self, joystick_id: int, axis_id: int, direction: str):
        """Handle joystick axis movement"""
        for binding in self.input_bindings:
            if (binding.joystick_axis == axis_id and
                binding.joystick_axis_direction == direction):
                self.logger.debug(f"Joystick {joystick_id} axis {axis_id} {direction} -> {binding.action}")
                self.action_triggered.emit(binding.action)

    def _handle_joystick_hat(self, joystick_id: int, hat_id: int, hat_value: tuple):
        """Handle joystick hat (D-pad) input"""
        x, y = hat_value

        # Map hat values to directions
        directions = []
        if x < 0:
            directions.append('left')
        elif x > 0:
            directions.append('right')
        if y > 0:
            directions.append('up')
        elif y < 0:
            directions.append('down')

        for direction in directions:
            for binding in self.input_bindings:
                if (binding.joystick_hat == hat_id and
                    binding.joystick_hat_direction == direction):
                    self.logger.debug(f"Joystick {joystick_id} hat {hat_id} {direction} -> {binding.action}")
                    self.action_triggered.emit(binding.action)

    def handle_key_press(self, key_code: int, scan_code: int = None):
        """Handle keyboard key press

        Args:
            key_code: Qt key code from event.key()
            scan_code: Native scan code from event.nativeScanCode() to differentiate left/right modifiers
        """
        if not self.keyboard_enabled:
            return

        from PyQt6.QtCore import Qt

        # Determine the actual key name for modifiers
        key_name = None
        if scan_code is not None:
            # Check for left/right shift/control/alt using scan codes (Linux X11)
            if key_code == Qt.Key.Key_Shift:
                if scan_code == 50:  # Left Shift
                    key_name = "Shift_L"
                elif scan_code == 62:  # Right Shift
                    key_name = "Shift_R"
            elif key_code == Qt.Key.Key_Control:
                if scan_code == 37:  # Left Control
                    key_name = "Control_L"
                elif scan_code == 105:  # Right Control
                    key_name = "Control_R"
            elif key_code == Qt.Key.Key_Alt:
                if scan_code == 64:  # Left Alt
                    key_name = "Alt_L"
                elif scan_code == 108:  # Right Alt
                    key_name = "Alt_R"

        self.logger.debug(f"Key pressed: {key_code}, scan: {scan_code}, name: {key_name}")

        # Check bindings
        for binding in self.input_bindings:
            # For modifier keys (Shift_L, Shift_R, etc.), match by the specific key_name
            if key_name and key_name in ["Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"]:
                if binding.key_name == key_name:
                    self.logger.debug(f"Matching binding found by modifier name: {binding.action}")
                    self.action_triggered.emit(binding.action)
                    return
            # For all other keys, match by key_code
            elif not key_name or key_name not in ["Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"]:
                if binding.key_code == key_code:
                    self.logger.debug(f"Matching binding found by code: {binding.action}")
                    self.action_triggered.emit(binding.action)
                    return

        self.logger.debug(f"No binding found for key: {key_code} ({key_name})")

    def add_binding(self, binding: InputBinding):
        """Add a new input binding"""
        self.input_bindings.append(binding)
        self.logger.info(f"Added input binding: {binding}")

    def remove_binding(self, action: InputAction, input_type: str = None):
        """Remove input bindings for an action"""
        original_count = len(self.input_bindings)

        if input_type == 'keyboard':
            self.input_bindings = [b for b in self.input_bindings
                                 if not (b.action == action and b.key_code is not None)]
        elif input_type == 'joystick':
            self.input_bindings = [b for b in self.input_bindings
                                 if not (b.action == action and
                                        (b.joystick_button is not None or
                                         b.joystick_axis is not None or
                                         b.joystick_hat is not None))]
        else:
            # Remove all bindings for this action
            self.input_bindings = [b for b in self.input_bindings if b.action != action]

        removed_count = original_count - len(self.input_bindings)
        self.logger.info(f"Removed {removed_count} binding(s) for action {action}")

    def get_bindings_for_action(self, action: InputAction) -> List[InputBinding]:
        """Get all bindings for a specific action"""
        return [binding for binding in self.input_bindings if binding.action == action]

    def set_joystick_enabled(self, enabled: bool):
        """Enable or disable joystick input"""
        self.joystick_enabled = enabled
        if enabled:
            self.start_polling()
        else:
            self.stop_polling()
        self.logger.info(f"Joystick input {'enabled' if enabled else 'disabled'}")

    def set_keyboard_enabled(self, enabled: bool):
        """Enable or disable keyboard input"""
        self.keyboard_enabled = enabled
        self.logger.info(f"Keyboard input {'enabled' if enabled else 'disabled'}")

    def get_joystick_info(self) -> List[Dict]:
        """Get information about connected joysticks"""
        info = []
        for i, joystick in enumerate(self.joysticks):
            info.append({
                'id': i,
                'name': joystick.get_name(),
                'buttons': joystick.get_numbuttons(),
                'axes': joystick.get_numaxes(),
                'hats': joystick.get_numhats()
            })
        return info

    def cleanup(self):
        """Clean up pygame resources"""
        self.stop_polling()
        try:
            for joystick in self.joysticks:
                joystick.quit()
            pygame.joystick.quit()
            pygame.quit()
            self.logger.info("Cleaned up input manager")
        except Exception as e:
            self.logger.error(f"Error cleaning up input manager: {e}")