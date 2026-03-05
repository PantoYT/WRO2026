"""
serial_interface.py
===================
Manages USB serial communication between the laptop and the LEGO Mindstorms hub.

The hub runs Pybricks and communicates via stdin/stdout over the USB cable.
On the laptop side this appears as a standard serial port (e.g. /dev/ttyACM0 on Linux,
COM3 on Windows, /dev/cu.usbmodem... on macOS).

Protocol:
- Every message is a single-line JSON object followed by \\n
- Both sides read and write on the same serial stream
- Messages are identified by the "type" field

Usage:
    from serial_interface import SerialInterface

    iface = SerialInterface(port="/dev/ttyACM0", baud=115200)
    iface.start()                       # starts background reader thread
    iface.send({"type": "SHOW_ICON", "icon": "HAPPY"})
    msg = iface.receive()               # non-blocking; returns None if nothing waiting
    iface.stop()
"""

import json
import queue
import threading
import time
import logging

# pyserial must be installed: pip install pyserial
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logging.warning("pyserial not installed – serial interface disabled. Install with: pip install pyserial")

logger = logging.getLogger(__name__)


class SerialInterface:
    """
    Thread-safe serial interface.

    A background thread continuously reads incoming lines and puts them in a queue.
    The main thread calls receive() to pop messages from the queue.
    send() can be called from any thread.
    """

    def __init__(self, port: str = None, baud: int = 115200, timeout: float = 0.1):
        """
        Args:
            port:    Serial port path. If None, auto-detect is attempted.
            baud:    Baud rate. Pybricks default is 115200.
            timeout: Read timeout in seconds (keep small to allow graceful shutdown).
        """
        self.port     = port or self._autodetect_port()
        self.baud     = baud
        self.timeout  = timeout

        self._serial:    serial.Serial | None = None
        self._rx_queue:  queue.Queue = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._running:   bool = False
        self._lock:      threading.Lock = threading.Lock()  # guards writes

    # ── Port detection ─────────────────────────────────────────────────────────

    @staticmethod
    def _autodetect_port() -> str | None:
        """
        Try to find the Mindstorms hub among available serial ports.
        The hub usually shows up as a USB CDC device.
        """
        if not SERIAL_AVAILABLE:
            return None
        for info in serial.tools.list_ports.comports():
            desc = (info.description or "").lower()
            manufacturer = (info.manufacturer or "").lower()
            # Pybricks / LEGO hub identifiers
            if any(k in desc for k in ("mindstorms", "pybricks", "lego", "cdc")):
                logger.info(f"Auto-detected hub port: {info.device}")
                return info.device
            if "lego" in manufacturer:
                return info.device
        logger.warning("Could not auto-detect hub port. Specify port manually.")
        return None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """
        Open the serial port and start the background reader thread.
        Returns True on success, False if serial is unavailable.
        """
        if not SERIAL_AVAILABLE:
            logger.error("Cannot start serial interface – pyserial not installed.")
            return False

        if not self.port:
            logger.error("No serial port available.")
            return False

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=self.timeout,
            )
            self._running = True
            self._reader_thread = threading.Thread(
                target=self._reader_loop,
                daemon=True,
                name="HubSerialReader",
            )
            self._reader_thread.start()
            logger.info(f"Serial interface started on {self.port} at {self.baud} baud.")
            return True
        except Exception as exc:
            logger.error(f"Failed to open serial port {self.port}: {exc}")
            return False

    def stop(self):
        """Cleanly shut down the serial connection and reader thread."""
        self._running = False
        if self._reader_thread:
            self._reader_thread.join(timeout=2)
        if self._serial and self._serial.is_open:
            self._serial.close()
        logger.info("Serial interface stopped.")

    # ── I/O ───────────────────────────────────────────────────────────────────

    def send(self, message: dict):
        """
        Serialize message as JSON and write it to the hub.
        Thread-safe.
        """
        if not self._serial or not self._serial.is_open:
            logger.warning(f"Serial not open, cannot send: {message}")
            return
        raw = json.dumps(message) + "\n"
        with self._lock:
            try:
                self._serial.write(raw.encode("utf-8"))
            except Exception as exc:
                logger.error(f"Serial write error: {exc}")

    def receive(self) -> dict | None:
        """
        Return the next message from the hub, or None if the queue is empty.
        Non-blocking.
        """
        try:
            return self._rx_queue.get_nowait()
        except queue.Empty:
            return None

    def receive_blocking(self, timeout: float = 5.0) -> dict | None:
        """
        Block until a message arrives or timeout expires.
        Returns the message dict or None on timeout.
        """
        try:
            return self._rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ── Background reader ─────────────────────────────────────────────────────

    def _reader_loop(self):
        """Background thread: continuously read lines and push to queue."""
        buffer = ""
        while self._running:
            try:
                if self._serial and self._serial.is_open:
                    chunk = self._serial.read(256).decode("utf-8", errors="replace")
                    buffer += chunk
                    # Process complete lines
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            self._parse_and_enqueue(line)
                else:
                    time.sleep(0.1)
            except Exception as exc:
                logger.error(f"Serial read error: {exc}")
                time.sleep(0.5)

    def _parse_and_enqueue(self, line: str):
        """Parse a JSON line and add it to the receive queue."""
        try:
            msg = json.loads(line)
            self._rx_queue.put(msg)
            logger.debug(f"Hub → Laptop: {msg}")
        except json.JSONDecodeError:
            logger.warning(f"Ignored non-JSON line from hub: {repr(line)}")

    # ── Simulation mode (no hub connected) ────────────────────────────────────

    def inject_fake_message(self, message: dict):
        """
        For testing without a real hub: inject a message as if it came from the hub.
        """
        self._rx_queue.put(message)
