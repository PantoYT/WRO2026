"""
main.py
=======
Laptop-side entry point for the Esperanto Robot project.

IMPORTANT – Windows / Tkinter threading note:
  Tkinter MUST run on the main thread on Windows.
  Therefore this script runs the Tkinter eye window on the main thread,
  and moves the robot logic (serial polling, mode manager) to a background thread.

Run with:
    python main.py [--port COM3] [--no-hub]

--no-hub   Run in demo mode without a physical hub.
           Type keys in the terminal: a=ButtonA  b=ButtonB  A=HoldA  B=HoldB  q=Quit
"""

import argparse
import logging
import os
import sys
import threading
import time

# ── Ensure imports work when running from the laptop/ directory ────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from serial_interface       import SerialInterface
from mode_manager           import ModeManager
from modules.flashcards     import FlashcardModule
from modules.poems          import PoemModule
from modules.songs          import SongModule
from modules.facts          import FactModule
from modules.zamenhof       import ZamenhofModule
from modules.pronunciation  import PronunciationModule
from modules.ai_assistant   import AIAssistantModule
from modules.audio_player   import AudioPlayer
from vision.eye_animation   import EyeAnimator
from vision.face_tracking   import FaceTracker

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("robot.log", encoding="utf-8"),
    ],
)
# Silence noisy third-party libraries
logging.getLogger("comtypes").setLevel(logging.WARNING)
logging.getLogger("comtypes.client._code_cache").setLevel(logging.WARNING)
logging.getLogger("comtypes.client._generate").setLevel(logging.WARNING)
logger = logging.getLogger("main")

# ── Resolve the data directory (sits next to the laptop/ folder) ───────────────
# Structure: WRO2026/
#               laptop/   ← we run from here
#               data/     ← data lives here
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
if not os.path.isdir(DATA_DIR):
    print(f"\n*** WARNING: data directory not found at {DATA_DIR}")
    print("    Make sure you extracted the zip so that data/ sits next to laptop/\n")
else:
    print(f"[OK] Data directory: {DATA_DIR}")


# ── CLI arguments ──────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(description="Esperanto Robot – Laptop Controller")
    parser.add_argument("--port",   default=None,
                        help="Serial port of the hub (e.g. COM3 on Windows, /dev/ttyACM0 on Linux)")
    parser.add_argument("--no-hub", action="store_true",
                        help="Run without physical hub (keyboard demo mode)")
    parser.add_argument("--camera", type=int, default=0,
                        help="Webcam index to use for face tracking (default: 0 = built-in). Use --camera -1 to disable.")
    return parser.parse_args()


# ── Build the system ───────────────────────────────────────────────────────────
def build_system(args):
    """Construct and wire together all subsystem objects. Returns (serial, manager, tracker, eyes)."""
    logger.info("Building system …")

    # Serial interface (hub communication)
    serial = SerialInterface(port=args.port)
    if not args.no_hub:
        ok = serial.start()
        if not ok:
            logger.warning("Could not connect to hub – continuing without it.")

    # Audio
    audio = AudioPlayer()

    # Eye animator – constructed here but NOT started yet.
    # start() must be called from the main thread (Tkinter requirement on Windows).
    eyes = EyeAnimator()

    # Webcam face tracker (background thread, safe)
    tracker = FaceTracker(eyes_callback=eyes.set_gaze,
                          camera_index=args.camera)

    # Learning modules
    flashcards    = FlashcardModule(serial=serial, audio=audio, eyes=eyes)
    poems         = PoemModule(serial=serial, audio=audio, eyes=eyes)
    songs         = SongModule(serial=serial, audio=audio, eyes=eyes)
    facts         = FactModule(serial=serial, audio=audio, eyes=eyes)
    zamenhof      = ZamenhofModule(serial=serial, audio=audio, eyes=eyes)
    pronunciation = PronunciationModule(serial=serial, audio=audio, eyes=eyes)
    ai_assistant  = AIAssistantModule(serial=serial, audio=audio, eyes=eyes)

    # Mode manager (state machine)
    manager = ModeManager()
    manager.serial        = serial
    manager.audio         = audio
    manager.eyes          = eyes
    manager.flashcards    = flashcards
    manager.poems         = poems
    manager.songs         = songs
    manager.facts         = facts
    manager.zamenhof      = zamenhof
    manager.pronunciation = pronunciation
    manager.ai_assistant  = ai_assistant

    return serial, manager, tracker, eyes


# ── Robot logic loop (runs in a background thread) ────────────────────────────
def robot_loop(serial: SerialInterface, manager: ModeManager, stop_event: threading.Event):
    """
    Background thread: polls serial messages and dispatches them to the mode manager.
    The eye animation tick is NOT called here – that runs on the main thread via Tkinter's
    after() scheduler inside EyeAnimator.
    """
    logger.info("Robot logic thread started.")
    while not stop_event.is_set():
        msg = serial.receive()
        while msg is not None:
            manager.handle_hub_message(msg)
            msg = serial.receive()
        time.sleep(0.02)   # 50 Hz polling


# ── Keyboard demo input (background thread) ───────────────────────────────────
def keyboard_demo_loop(serial: SerialInterface, stop_event: threading.Event):
    """Allow keyboard input to simulate hub button presses when no hub is connected."""
    def _prompt():
        print("\n[Demo] a=Next  b=Confirm  A=Back  B=Repeat  q=Quit  > ", end="", flush=True)

    _prompt()
    while not stop_event.is_set():
        try:
            key = input().strip()
        except EOFError:
            break
        if key == "a":
            serial.inject_fake_message({"type": "BUTTON_A_PRESS", "hold": False})
        elif key == "b":
            serial.inject_fake_message({"type": "BUTTON_B_PRESS", "hold": False})
        elif key == "A":
            serial.inject_fake_message({"type": "BUTTON_A_PRESS", "hold": True})
        elif key == "B":
            serial.inject_fake_message({"type": "BUTTON_B_PRESS", "hold": True})
        elif key == "q":
            logger.info("Quit requested by user.")
            stop_event.set()
            os._exit(0)
        elif key == "":
            pass   # just re-show prompt on empty Enter
        else:
            print(f"  Unknown key: '{key}'")
        _prompt()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args       = parse_args()
    stop_event = threading.Event()

    serial, manager, tracker, eyes = build_system(args)

    # Start face tracker (background thread – safe on any thread)
    if args.camera >= 0:
        tracker.start()
    else:
        logger.info("Face tracking disabled (--camera -1).")

    # Start serial polling in a background thread
    t_robot = threading.Thread(
        target=robot_loop,
        args=(serial, manager, stop_event),
        daemon=True,
        name="RobotLogic",
    )
    t_robot.start()

    # Start keyboard demo input in a background thread
    if args.no_hub:
        t_kbd = threading.Thread(
            target=keyboard_demo_loop,
            args=(serial, stop_event),
            daemon=True,
            name="KeyboardDemo",
        )
        t_kbd.start()
        # Simulate the hub sending its ready message
        serial.inject_fake_message({"type": "HUB_READY"})

    # ── Start the Tkinter eye window ON THE MAIN THREAD ───────────────────────
    # eyes.start() calls tkinter.mainloop() which blocks until the window closes.
    # Everything else must already be running in background threads before this call.
    logger.info("Starting eye animation window (main thread).")
    try:
        eyes.start()          # blocks here until window is closed
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Window closed – shutting down.")
        stop_event.set()
        serial.stop()
        tracker.stop()
        logger.info("Goodbye!")