"""
modules/audio_player.py
========================
Handles all audio output:
  - Text-to-speech via pyttsx3 (offline, Windows SAPI5)
  - Audio file playback via pygame.mixer

IMPORTANT - Windows COM / pyttsx3 threading:
  pyttsx3 uses Windows SAPI5 which requires COM and must run on a single
  dedicated thread. We solve this with a TTS worker thread that owns the
  engine and processes a queue of text strings.
"""

import logging
import os
import queue
import threading

logger = logging.getLogger(__name__)

try:
    import pyttsx3
    TTS_OFFLINE = True
except ImportError:
    TTS_OFFLINE = False
    logger.warning("pyttsx3 not installed. pip install pyttsx3")

try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except Exception as e:
    PYGAME_AVAILABLE = False
    logger.warning(f"pygame mixer unavailable: {e}")


class AudioPlayer:
    """
    Thread-safe audio output.

    pyttsx3 runs in its own worker thread (required on Windows).
    speak() just puts text onto a queue - never blocks the caller.
    """

    def __init__(self):
        self._last_text = ""
        self._last_file = ""

        # Queue for TTS requests: items are strings, or None to stop the thread
        self._tts_queue: queue.Queue = queue.Queue()

        # Start the dedicated TTS worker thread
        if TTS_OFFLINE:
            self._tts_thread = threading.Thread(
                target=self._tts_worker,
                daemon=True,
                name="TTSWorker",
            )
            self._tts_thread.start()
        else:
            self._tts_thread = None

    # ── TTS worker (runs on its own thread, owns the pyttsx3 engine) ──────────

    def _tts_worker(self):
        """
        Dedicated thread for pyttsx3.
        Initialises the engine here (same thread = COM safety on Windows).
        Processes text items from the queue one at a time.
        """
        try:
            engine = pyttsx3.init()
            rate = engine.getProperty("rate")
            engine.setProperty("rate", max(100, rate - 30))
            logger.info("pyttsx3 TTS engine ready.")
        except Exception as exc:
            logger.error(f"pyttsx3 init failed: {exc}")
            return

        while True:
            try:
                text = self._tts_queue.get(timeout=1)
            except queue.Empty:
                continue

            if text is None:
                break   # shutdown signal

            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as exc:
                logger.error(f"pyttsx3 speak error: {exc}")

            self._tts_queue.task_done()

    # ── Public API ─────────────────────────────────────────────────────────────

    def speak(self, text: str):
        """Queue text for speech. Returns immediately (non-blocking)."""
        if not text:
            return
        self._last_text = text
        logger.info(f"[TTS] {text}")

        if TTS_OFFLINE and self._tts_thread and self._tts_thread.is_alive():
            # Clear any pending items so new speech isn't delayed
            while not self._tts_queue.empty():
                try:
                    self._tts_queue.get_nowait()
                except queue.Empty:
                    break
            self._tts_queue.put(text)
        else:
            logger.warning(f"[TTS no engine] {text}")

    def play_file(self, path: str):
        """Play an audio file (MP3 or WAV) in a background thread."""
        if not os.path.exists(path):
            logger.error(f"Audio file not found: {path}")
            return
        self._last_file = path
        t = threading.Thread(target=self._play_blocking, args=(path,), daemon=True)
        t.start()

    def _play_blocking(self, path: str):
        if not PYGAME_AVAILABLE:
            logger.warning(f"pygame unavailable, cannot play {path}")
            return
        try:
            import time
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
        except Exception as exc:
            logger.error(f"Audio playback error: {exc}")

    def stop(self):
        """Stop any currently playing audio."""
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    def repeat_last(self):
        """Repeat the last spoken text or played file."""
        if self._last_file:
            self.play_file(self._last_file)
        elif self._last_text:
            self.speak(self._last_text)