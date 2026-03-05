"""
vision/face_tracking.py
=======================
Detects human faces using the webcam and sends normalised gaze direction
to the eye animator so the robot "looks at" the user.

Also detects when a person enters/leaves the frame:
  - Person detected → sends WAKE_EVENT to the hub (wakes from hibernation)
  - Person leaves    → can trigger idle mode

Dependencies:
    pip install opencv-python

Face detection uses OpenCV's built-in Haar Cascade classifier (offline, no API key needed).

Usage:
    from vision.face_tracking import FaceTracker
    from vision.eye_animation import EyeAnimator

    eyes    = EyeAnimator()
    tracker = FaceTracker(eyes_callback=eyes.set_gaze)
    tracker.set_wake_callback(lambda: serial.inject_fake_message({"type":"WAKE_EVENT"}))
    tracker.start()
    # ... later ...
    tracker.stop()
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("opencv-python not installed – face tracking disabled. pip install opencv-python")


class FaceTracker:
    """
    Runs webcam capture and face detection in a background thread.

    Calls eyes_callback(x_norm, y_norm) whenever a face is detected,
    where x_norm and y_norm are in the range -1.0 .. 1.0.

    Calls wake_callback() when a face appears after being absent.
    """

    def __init__(self, eyes_callback=None, wake_callback=None, camera_index: int = 0):
        """
        Args:
            eyes_callback:  fn(x_norm: float, y_norm: float) – called each frame with face position.
            wake_callback:  fn() – called when a face is first detected (e.g. to wake the hub).
            camera_index:   OpenCV camera index (0 = default webcam).
        """
        self._eyes_callback  = eyes_callback
        self._wake_callback  = wake_callback
        self._camera_index   = camera_index

        self._thread:   threading.Thread | None = None
        self._running:  bool = False
        self._face_present_last_frame: bool = False

    def set_wake_callback(self, cb):
        """Set or update the wake callback after construction."""
        self._wake_callback = cb

    def start(self):
        """Start the face detection thread."""
        if not CV2_AVAILABLE:
            logger.warning("Face tracking not started: opencv not available.")
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._tracking_loop, daemon=True, name="FaceTracker"
        )
        self._thread.start()
        logger.info("Face tracker started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Face tracker stopped.")

    # ── Background tracking loop ───────────────────────────────────────────────

    def _tracking_loop(self):
        """Capture frames from the webcam and run Haar face detection."""
        cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            logger.error(f"Could not open camera {self._camera_index}.")
            return

        # Load the pre-trained face detector (bundled with OpenCV)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        detector     = cv2.CascadeClassifier(cascade_path)

        logger.info("Webcam opened successfully.")

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            frame_h, frame_w = frame.shape[:2]

            # Convert to grey for faster detection
            grey  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(
                grey,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60),
            )

            face_detected = len(faces) > 0

            # ── Wake event ────────────────────────────────────────────────────
            if face_detected and not self._face_present_last_frame:
                logger.info("Face detected – sending wake event.")
                if self._wake_callback:
                    self._wake_callback()

            self._face_present_last_frame = face_detected

            # ── Gaze update ───────────────────────────────────────────────────
            if face_detected and self._eyes_callback:
                # Use the largest face (closest to camera)
                largest = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = largest

                # Face centre in pixel coordinates
                face_cx = fx + fw // 2
                face_cy = fy + fh // 2

                # Normalise to -1..1  (left=-1, right=+1; up=-1, down=+1)
                x_norm = (face_cx / frame_w - 0.5) * 2.0
                y_norm = (face_cy / frame_h - 0.5) * 2.0

                self._eyes_callback(x_norm, y_norm)
            elif not face_detected and self._eyes_callback:
                # No face → slowly return gaze to centre
                self._eyes_callback(0.0, 0.0)

            # ~15 fps is plenty for face tracking
            time.sleep(1 / 15)

        cap.release()
        logger.info("Webcam released.")
