"""
modules/poems.py
================
POETRY MODE – Recite Esperanto poems.

Poems are stored as plain .txt files in data/poems/
Each file = one poem.  The filename is the poem title.

Button A → next poem
Button B → hear the current poem read aloud
"""

import glob
import logging
import os

logger = logging.getLogger(__name__)

POEMS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "poems")


class PoemModule:
    def __init__(self, serial, audio, eyes):
        self.serial = serial
        self.audio  = audio
        self.eyes   = eyes
        self._poems: list[dict] = []   # [{"title": str, "text": str}]
        self._index: int = 0

    def start(self):
        self._load_poems()
        if not self._poems:
            self.audio.speak("Neniu poemo trovita. Bonvolu aldoni .txt dosierojn en data/poems/")
            return
        self._announce_current()

    def stop(self):
        self.audio.stop()

    def on_button_a(self):
        """Advance to the next poem."""
        if not self._poems:
            return
        self._index = (self._index + 1) % len(self._poems)
        self._announce_current()

    def on_button_b(self):
        """Read the current poem aloud."""
        if not self._poems:
            return
        poem = self._poems[self._index]
        self.audio.speak(poem["text"])

    def _announce_current(self):
        if not self._poems:
            return
        poem = self._poems[self._index]
        logger.info(f"Poem [{self._index+1}/{len(self._poems)}]: {poem['title']}")
        self.eyes.show_text(poem["title"])
        self.audio.speak(f"Poemo: {poem['title']}")
        if self.serial:
            self.serial.send({"type": "SHOW_ICON", "icon": "SMILE"})

    def _load_poems(self):
        self._poems = []
        for filepath in sorted(glob.glob(os.path.join(POEMS_DIR, "*.txt"))):
            title = os.path.splitext(os.path.basename(filepath))[0]
            try:
                with open(filepath, encoding="utf-8") as f:
                    text = f.read().strip()
                self._poems.append({"title": title, "text": text})
            except Exception as exc:
                logger.error(f"Failed to load poem {filepath}: {exc}")
        logger.info(f"Loaded {len(self._poems)} poem(s).")
