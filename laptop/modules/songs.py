"""
modules/songs.py
================
SONG MODE – Play Esperanto songs.

Audio files (MP3 or WAV) are stored in data/songs/
Button A → next song
Button B → play / pause current song
"""

import glob
import logging
import os

logger = logging.getLogger(__name__)

SONGS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "songs")


class SongModule:
    def __init__(self, serial, audio, eyes):
        self.serial = serial
        self.audio  = audio
        self.eyes   = eyes
        self._songs: list[str] = []   # list of file paths
        self._index: int = 0
        self._playing: bool = False

    def start(self):
        self._songs = sorted(
            glob.glob(os.path.join(SONGS_DIR, "*.mp3")) +
            glob.glob(os.path.join(SONGS_DIR, "*.wav"))
        )
        if not self._songs:
            self.audio.speak("Neniu kanto trovita. Bonvolu aldoni mp3 dosierojn en data/songs/")
            return
        logger.info(f"Loaded {len(self._songs)} song(s).")
        self._announce_current()

    def stop(self):
        self.audio.stop()
        self._playing = False

    def on_button_a(self):
        """Next song."""
        if not self._songs:
            return
        self.audio.stop()
        self._playing = False
        self._index = (self._index + 1) % len(self._songs)
        self._announce_current()

    def on_button_b(self):
        """Play the current song."""
        if not self._songs:
            return
        self._playing = True
        self.audio.play_file(self._songs[self._index])

    def _announce_current(self):
        if not self._songs:
            return
        name = os.path.splitext(os.path.basename(self._songs[self._index]))[0]
        logger.info(f"Song [{self._index+1}/{len(self._songs)}]: {name}")
        self.eyes.show_text(name)
        self.audio.speak(f"Kanto: {name}")
        if self.serial:
            self.serial.send({"type": "SHOW_ICON", "icon": "HAPPY"})
