"""
modules/flashcards.py
=====================
FLASHCARD MODE – Esperanto vocabulary practice.

Behaviour:
  - Loads word pairs from CSV files in data/vocabulary/
  - Displays the Esperanto word on screen (via eye display + TTS)
  - Button A → reveal the translation
  - Button B → hear pronunciation (TTS repeat)
  - After revealing, Button A advances to the next card

CSV format (data/vocabulary/basic.csv):
    esperanto,translation,notes
    hundo,dog,common noun
    kato,cat,
    ...

The module randomly shuffles cards so each session is different.
"""

import csv
import glob
import logging
import os
import random
import threading

logger = logging.getLogger(__name__)

# Path relative to the project root (laptop/ is the working directory)
VOCAB_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "vocabulary")


class FlashcardModule:
    """Manage flashcard sessions."""

    def __init__(self, serial, audio, eyes):
        self.serial = serial
        self.audio  = audio
        self.eyes   = eyes

        # All loaded word pairs: list of {"esperanto": str, "translation": str}
        self._cards: list[dict] = []
        self._index: int = 0
        self._revealed: bool = False   # has the translation been shown yet?

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        """Called when entering Flashcard mode."""
        self._load_vocabulary()
        if not self._cards:
            self.audio.speak("Neniu vortaro trovita. Bonvolu aldoni dosierojn en data/vocabulary/")
            return
        random.shuffle(self._cards)
        self._index    = 0
        self._revealed = False
        self._show_current_card()

    def stop(self):
        """Called when leaving Flashcard mode."""
        logger.info("Flashcard mode stopped.")

    # ── Button handlers ────────────────────────────────────────────────────────

    def on_button_a(self):
        """
        Short A:
          - If translation not yet revealed → reveal it
          - If already revealed → advance to next card
        """
        if not self._cards:
            return
        if not self._revealed:
            self._reveal_translation()
        else:
            self._next_card()

    def on_button_b(self):
        """Short B: hear the Esperanto word pronounced."""
        if not self._cards:
            return
        word = self._cards[self._index]["esperanto"]
        self.audio.speak(word)

    def on_hold_b(self):
        """Hold B: repeat last audio (handled centrally, but we hook it anyway)."""
        self.audio.repeat_last()

    # ── Card logic ─────────────────────────────────────────────────────────────

    def _show_current_card(self):
        """Display the Esperanto side of the current card."""
        if not self._cards:
            return
        card = self._cards[self._index]
        word = card["esperanto"]

        logger.info(f"Flashcard [{self._index+1}/{len(self._cards)}]: {word}")
        self.eyes.show_text(word)
        self.audio.speak(f"Kio estas: {word}?")

        # Show a "thinking" icon on the hub
        if self.serial:
            self.serial.send({"type": "SHOW_ICON", "icon": "CIRCLE"})

    def _reveal_translation(self):
        """Show the translation of the current card."""
        if not self._cards:
            return
        card  = self._cards[self._index]
        word  = card["esperanto"]
        trans = card["translation"]

        self._revealed = True
        logger.info(f"Revealed: {word} = {trans}")
        self.eyes.show_text(trans)
        self.audio.speak(f"{word} signifas {trans}")

        if self.serial:
            self.serial.send({"type": "SHOW_ICON", "icon": "HAPPY"})

    def _next_card(self):
        """Move to the next card, wrapping around at the end."""
        self._index    = (self._index + 1) % len(self._cards)
        self._revealed = False
        self._show_current_card()

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_vocabulary(self):
        """Load all CSV vocabulary files from the vocabulary directory."""
        self._cards = []
        pattern = os.path.join(VOCAB_DIR, "*.csv")
        files   = glob.glob(pattern)

        if not files:
            logger.warning(f"No vocabulary CSV files found in {VOCAB_DIR}")
            return

        for filepath in files:
            self._load_csv(filepath)

        logger.info(f"Loaded {len(self._cards)} flashcards from {len(files)} file(s).")

    def _load_csv(self, filepath: str):
        """Parse a single CSV vocabulary file."""
        try:
            with open(filepath, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Accept files with or without a "notes" column
                    esperanto   = row.get("esperanto", "").strip()
                    translation = row.get("translation", "").strip()
                    if esperanto and translation:
                        self._cards.append({
                            "esperanto":   esperanto,
                            "translation": translation,
                            "notes":       row.get("notes", "").strip(),
                        })
        except Exception as exc:
            logger.error(f"Failed to load vocabulary file {filepath}: {exc}")
