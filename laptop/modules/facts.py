"""
modules/facts.py
================
LANGUAGE FACT MODE – share interesting facts about the Esperanto language.

Facts are stored one-per-line in data/facts/language_facts.txt
Button A → next fact
Button B → repeat current fact
"""

import logging
import os
import random

logger = logging.getLogger(__name__)

FACTS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "facts", "language_facts.txt")


class FactModule:
    def __init__(self, serial, audio, eyes):
        self.serial = serial
        self.audio  = audio
        self.eyes   = eyes
        self._facts: list[str] = []
        self._index: int = 0

    def start(self):
        self._load_facts()
        if not self._facts:
            self.audio.speak("Neniu fakto trovita.")
            return
        random.shuffle(self._facts)
        self._index = 0
        self._deliver_current()

    def stop(self):
        pass

    def on_button_a(self):
        if not self._facts:
            return
        self._index = (self._index + 1) % len(self._facts)
        self._deliver_current()

    def on_button_b(self):
        if self._facts:
            self.audio.speak(self._facts[self._index])

    def _deliver_current(self):
        if not self._facts:
            return
        fact = self._facts[self._index]
        logger.info(f"Fact [{self._index+1}/{len(self._facts)}]: {fact[:60]}…")
        self.eyes.show_text("Fakto!")
        self.audio.speak(fact)
        if self.serial:
            self.serial.send({"type": "SHOW_ICON", "icon": "CIRCLE"})

    def _load_facts(self):
        self._facts = []
        if not os.path.exists(FACTS_FILE):
            logger.warning(f"Facts file not found: {FACTS_FILE}")
            return
        with open(FACTS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    self._facts.append(line)
        logger.info(f"Loaded {len(self._facts)} facts.")
