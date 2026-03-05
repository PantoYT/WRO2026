"""
mode_manager.py
===============
The ModeManager is the central controller for the laptop side of the robot.

It:
  - maintains the current active mode
  - dispatches hub button events to the active mode
  - handles transitions between modes (menu navigation)
  - sends display / animation commands back to the hub and eye renderer

Modes:
  MENU          – top-level navigation menu
  FLASHCARD     – vocabulary flashcard practice
  POETRY        – recite Esperanto poems
  SONG          – play Esperanto songs
  FACT          – language curiosity facts
  ZAMENHOF      – historical facts about Zamenhof
  PRONUNCIATION – pronunciation training
  AI_ASSISTANT  – AI chatbot restricted to Esperanto topics
"""

import logging
import time
from enum import Enum, auto

logger = logging.getLogger(__name__)


# ── Mode identifiers ───────────────────────────────────────────────────────────

class Mode(Enum):
    MENU          = auto()
    FLASHCARD     = auto()
    POETRY        = auto()
    SONG          = auto()
    FACT          = auto()
    ZAMENHOF      = auto()
    PRONUNCIATION = auto()
    AI_ASSISTANT  = auto()
    HIBERNATION   = auto()


# ── Menu definition (order = A-button navigation order) ───────────────────────

MENU_ITEMS = [
    (Mode.FLASHCARD,     "Flaŝkartoj",   "HEART"),      # Flashcards
    (Mode.POETRY,        "Poemoj",        "SMILE"),      # Poems
    (Mode.SONG,          "Kantoj",        "HAPPY"),      # Songs
    (Mode.FACT,          "Faktoj",        "CIRCLE"),     # Language facts
    (Mode.ZAMENHOF,      "Zamenhof",      "ARROW_UP"),   # Zamenhof history
    (Mode.PRONUNCIATION, "Prononco",      "SQUARE"),     # Pronunciation
    (Mode.AI_ASSISTANT,  "AI Asistanto",  "ARROW_RIGHT"),# AI assistant
]


class ModeManager:
    """
    Central state machine.

    Wiring (set these after construction):
        manager.serial    = SerialInterface instance
        manager.audio     = AudioPlayer instance
        manager.eyes      = EyeAnimator instance
        manager.flashcards= FlashcardModule instance
        ... etc.
    """

    def __init__(self):
        self.current_mode  = Mode.MENU
        self.menu_index    = 0          # which menu item is highlighted
        self._active_module = None      # the currently running module object

        # References to subsystems – injected after construction
        self.serial        = None
        self.audio         = None
        self.eyes          = None
        self.flashcards    = None
        self.poems         = None
        self.songs         = None
        self.facts         = None
        self.zamenhof      = None
        self.pronunciation = None
        self.ai_assistant  = None

        self._last_activity = time.time()

    # ── Public entry points ────────────────────────────────────────────────────

    def handle_hub_message(self, msg: dict):
        """
        Called by the main loop whenever a JSON message arrives from the hub.
        Dispatches to the appropriate handler based on message type.
        """
        msg_type = msg.get("type", "")
        hold     = msg.get("hold", False)

        logger.debug(f"Hub message: {msg_type}, hold={hold}, mode={self.current_mode}")
        self._last_activity = time.time()

        if msg_type == "HUB_READY":
            self._on_hub_ready()

        elif msg_type == "BUTTON_A_PRESS":
            if hold:
                self._on_hold_a()
            else:
                self._on_press_a()

        elif msg_type == "BUTTON_B_PRESS":
            if hold:
                self._on_hold_b()
            else:
                self._on_press_b()

        elif msg_type in ("WAKE_EVENT", "IDLE_TIMEOUT"):
            self._on_wake() if msg_type == "WAKE_EVENT" else self._on_idle_timeout()

    def enter_mode(self, mode: Mode):
        """Transition to a new mode, cleaning up the previous one."""
        logger.info(f"Entering mode: {mode.name}")

        # Stop any currently running module
        if self._active_module and hasattr(self._active_module, "stop"):
            self._active_module.stop()

        self.current_mode = mode

        # Set eye expression for this mode
        self._set_eyes_for_mode(mode)

        # Activate the module
        module = self._get_module(mode)
        self._active_module = module
        if module and hasattr(module, "start"):
            module.start()

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_hub_ready(self):
        """Hub just connected – show welcome and go to menu."""
        logger.info("Hub is ready – entering menu.")
        self._show_menu_item()
        if self.audio:
            self.audio.speak("Bonvenon! Mi estas via Esperanto-roboto.")
        if self.eyes:
            self.eyes.set_expression("happy")

    def _on_press_a(self):
        """Short press A: next menu item (in menu) or mode-specific next."""
        if self.current_mode == Mode.MENU:
            self.menu_index = (self.menu_index + 1) % len(MENU_ITEMS)
            self._show_menu_item()
        elif self._active_module and hasattr(self._active_module, "on_button_a"):
            self._active_module.on_button_a()

    def _on_press_b(self):
        """Short press B: confirm selection (in menu) or mode-specific confirm."""
        if self.current_mode == Mode.MENU:
            _, label, _ = MENU_ITEMS[self.menu_index]
            logger.info(f"User selected: {label}")
            self.enter_mode(MENU_ITEMS[self.menu_index][0])
        elif self._active_module and hasattr(self._active_module, "on_button_b"):
            self._active_module.on_button_b()

    def _on_hold_a(self):
        """Hold A: go back to menu from any mode."""
        if self.current_mode != Mode.MENU:
            self.enter_mode(Mode.MENU)
            self._show_menu_item()
            if self.audio:
                self.audio.speak("Reen al la menuo.")
        elif self._active_module and hasattr(self._active_module, "on_hold_a"):
            self._active_module.on_hold_a()

    def _on_hold_b(self):
        """Hold B: repeat last audio in any mode."""
        if self.audio:
            self.audio.repeat_last()
        if self._active_module and hasattr(self._active_module, "on_hold_b"):
            self._active_module.on_hold_b()

    def _on_idle_timeout(self):
        """Hub reported inactivity – enter hibernation."""
        logger.info("Entering hibernation mode.")
        self.current_mode = Mode.HIBERNATION
        if self.eyes:
            self.eyes.set_expression("sleeping")
        if self._active_module and hasattr(self._active_module, "stop"):
            self._active_module.stop()

    def _on_wake(self):
        """Wake from hibernation."""
        logger.info("Waking from hibernation.")
        self.enter_mode(Mode.MENU)
        self._show_menu_item()
        if self.eyes:
            self.eyes.set_expression("idle")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _show_menu_item(self):
        """Display the current menu item name and icon on the hub + audio."""
        mode, label, icon = MENU_ITEMS[self.menu_index]
        # Tell the hub to show the icon
        if self.serial:
            self.serial.send({"type": "SHOW_ICON", "icon": icon})
        # Optionally announce via TTS
        if self.audio:
            self.audio.speak(label)
        logger.info(f"Menu: [{self.menu_index}] {label}")

    def _set_eyes_for_mode(self, mode: Mode):
        """Map mode → eye expression."""
        expression_map = {
            Mode.MENU:          "idle",
            Mode.FLASHCARD:     "thinking",
            Mode.POETRY:        "happy",
            Mode.SONG:          "happy",
            Mode.FACT:          "thinking",
            Mode.ZAMENHOF:      "thinking",
            Mode.PRONUNCIATION: "speaking",
            Mode.AI_ASSISTANT:  "thinking",
            Mode.HIBERNATION:   "sleeping",
        }
        expr = expression_map.get(mode, "idle")
        if self.eyes:
            self.eyes.set_expression(expr)

    def _get_module(self, mode: Mode):
        """Return the module instance for a given mode."""
        return {
            Mode.FLASHCARD:     self.flashcards,
            Mode.POETRY:        self.poems,
            Mode.SONG:          self.songs,
            Mode.FACT:          self.facts,
            Mode.ZAMENHOF:      self.zamenhof,
            Mode.PRONUNCIATION: self.pronunciation,
            Mode.AI_ASSISTANT:  self.ai_assistant,
        }.get(mode)
