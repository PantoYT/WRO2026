"""
hub_main.py
===========
LEGO Mindstorms 51515 Hub code for the Esperanto Robot project.
Runs under Pybricks MicroPython on the official LEGO hub.

The hub serves as the PHYSICAL INTERFACE ONLY:
  - Detects button presses (A left, B right)
  - Sends JSON messages over USB serial to the laptop
  - Receives JSON commands from the laptop to control display
  - Auto-sleeps after 1 minute of inactivity (power saving)
  - Shows status on 5×5 LED matrix and RGB light

Communication Protocol:
  - USB serial, 115200 baud, JSON messages, newline-delimited
  - Hub → Laptop: {"type": "BUTTON_A_PRESS", "hold": false/true}
  - Laptop → Hub: {"type": "SHOW_ICON", "icon": "HAPPY"}

Architecture Notes:
  - No AI, no state machine, no complexity on the hub
  - All logic happens on the laptop
  - This design allows easy updates and debugging
"""

from pybricks.hubs import PrimeHub
from pybricks.parameters import Button, Icon, Color
from pybricks.tools import wait, StopWatch
import ujson
import sys

# ── Hardware setup ─────────────────────────────────────────────────────────────
hub = PrimeHub()

# ── Constants ──────────────────────────────────────────────────────────────────
HOLD_THRESHOLD_MS = 800   # Button held > 800ms counts as "hold"
POLL_INTERVAL_MS  = 50    # Poll buttons every 50ms (20 Hz)
SLEEP_TIMEOUT_MS  = 60000 # Auto-sleep after 1 minute of inactivity

# ── Icon map: names → Pybricks Icon constants ───────────────────────────────--
ICONS = {
    "HAPPY":    Icon.HAPPY,
    "SAD":      Icon.SAD,
    "HEART":    Icon.HEART,
    "SMILE":    Icon.SMILE,
    "STALLED":  Icon.STALLED,
    "ARROW_UP": Icon.UP,
    "ARROW_DOWN": Icon.DOWN,
    "ARROW_LEFT": Icon.LEFT,
    "ARROW_RIGHT": Icon.RIGHT,
    "CIRCLE":   Icon.CIRCLE,
    "SQUARE":   Icon.SQUARE,
}

# ── State ──────────────────────────────────────────────────────────────────────
sleeping = False

# ── Helper: send a JSON message to the laptop over USB serial ──────────────────
def send(msg: dict):
    """Serialize msg as JSON and write it to stdout (USB serial) with a newline."""
    sys.stdout.write(ujson.dumps(msg) + "\n")

# ── Helper: read one JSON message from stdin (non-blocking) ───────────────────
def try_read_message():
    """
    Try to read a line from stdin.
    Returns parsed dict if a full line is available, else None.
    Pybricks stdin.readline() returns '' if nothing is available yet.
    """
    try:
        line = sys.stdin.readline()
        if line:
            return ujson.loads(line.strip())
    except Exception:
        pass  # ignore parse errors
    return None

# ── Helper: process a command sent from the laptop ────────────────────────────
def handle_command(cmd: dict):
    """React to commands received from the laptop."""
    global sleeping

    cmd_type = cmd.get("type", "")

    if cmd_type == "SHOW_ICON":
        # Display a named icon on the 5×5 LED matrix
        icon_name = cmd.get("icon", "SMILE")
        icon = ICONS.get(icon_name, Icon.SMILE)
        hub.display.icon(icon)

    elif cmd_type == "SHOW_TEXT":
        # Scroll short text across the display
        text = cmd.get("text", "")
        hub.display.text(text, on=500, off=50)

    elif cmd_type == "ENTER_SLEEP":
        # Dim the display and flag as sleeping
        hub.display.off()
        sleeping = True

    elif cmd_type == "WAKE_UP":
        # Turn display back on
        sleeping = False
        hub.display.icon(Icon.CIRCLE)

    elif cmd_type == "SET_COLOR":
        # Change the hub status light color
        color_name = cmd.get("color", "WHITE")
        color_map = {
            "WHITE": Color.WHITE, "BLUE": Color.BLUE,
            "GREEN": Color.GREEN, "RED": Color.RED,
            "YELLOW": Color.YELLOW, "ORANGE": Color.ORANGE,
        }
        hub.light.on(color_map.get(color_name, Color.WHITE))

# ── Main loop ──────────────────────────────────────────────────────────────────
def main():
    global sleeping

    # Show startup icon
    hub.display.icon(Icon.CIRCLE)
    hub.light.on(Color.BLUE)

    # Send a boot message so the laptop knows the hub is ready
    send({"type": "HUB_READY", "version": "1.0"})

    # Timers for hold detection and inactivity
    a_timer  = StopWatch()
    b_timer  = StopWatch()
    idle_timer = StopWatch()
    a_was_pressed = False
    b_was_pressed = False

    while True:
        # ── Read any command from the laptop ──────────────────────────────────
        cmd = try_read_message()
        if cmd:
            handle_command(cmd)
            idle_timer.reset()  # laptop sent something → not idle

        # ── Check buttons ─────────────────────────────────────────────────────
        pressed = hub.buttons.pressed()

        # Button A (left button on the hub)
        if Button.LEFT in pressed:
            if not a_was_pressed:
                a_was_pressed = True
                a_timer.reset()
        else:
            if a_was_pressed:
                a_was_pressed = False
                hold = a_timer.time() >= HOLD_THRESHOLD_MS
                if sleeping:
                    # Wake up on any button press
                    sleeping = False
                    send({"type": "WAKE_EVENT", "source": "button"})
                else:
                    send({"type": "BUTTON_A_PRESS", "hold": hold})
                idle_timer.reset()

        # Button B (right button on the hub)
        if Button.RIGHT in pressed:
            if not b_was_pressed:
                b_was_pressed = True
                b_timer.reset()
        else:
            if b_was_pressed:
                b_was_pressed = False
                hold = b_timer.time() >= HOLD_THRESHOLD_MS
                if sleeping:
                    sleeping = False
                    send({"type": "WAKE_EVENT", "source": "button"})
                else:
                    send({"type": "BUTTON_B_PRESS", "hold": hold})
                idle_timer.reset()

        # ── Auto-sleep after inactivity ───────────────────────────────────────
        if not sleeping and idle_timer.time() > SLEEP_TIMEOUT_MS:
            sleeping = True
            send({"type": "IDLE_TIMEOUT"})
            hub.display.off()

        wait(POLL_INTERVAL_MS)

# ── Entry point ────────────────────────────────────────────────────────────────
main()
