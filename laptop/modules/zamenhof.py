"""
modules/zamenhof.py
===================
ZAMENHOF MODE – historical facts about Ludwik Lazarz Zamenhof, creator of Esperanto.

Facts are stored in data/facts/zamenhof_facts.txt  (one fact per line).
Button A → next fact
Button B → hear current fact again
"""

import logging
import os
import random

logger = logging.getLogger(__name__)

ZAMENHOF_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "facts", "zamenhof_facts.txt"
)


class ZamenhofModule:
    def __init__(self, serial, audio, eyes):
        self.serial = serial
        self.audio  = audio
        self.eyes   = eyes
        self._facts: list[str] = []
        self._index: int = 0

    def start(self):
        self._load_facts()
        if not self._facts:
            self.audio.speak("Neniu fakto pri Zamenhof trovita.")
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
        logger.info(f"Zamenhof fact [{self._index+1}/{len(self._facts)}]")
        self.eyes.show_text("Zamenhof")
        self.audio.speak(fact)
        if self.serial:
            self.serial.send({"type": "SHOW_ICON", "icon": "ARROW_UP"})

    def _load_facts(self):
        self._facts = []
        if not os.path.exists(ZAMENHOF_FILE):
            logger.warning(f"Zamenhof facts file not found: {ZAMENHOF_FILE}")
            # Provide a built-in minimal set so the mode is never empty
            self._facts = [
                "Ludwik Lazarz Zamenhof naskiĝis la 15-an de decembro 1859 en Białystok.",
                "Zamenhof publikigis Esperanton en 1887 sub la pseŭdonimo 'Doktoro Esperanto'.",
                "Zamenhof estis okulisto de profesio.",
                "Li kreskis en urbo kie kvar lingvoj konkuris: la rusa, pola, jida kaj germana.",
                "La unua libro de Esperanto estis konata kiel la 'Unua Libro'.",
                "Zamenhof mortis la 14-an de aprilo 1917 en Varsovio.",
            ]
            return
        with open(ZAMENHOF_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    self._facts.append(line)
        logger.info(f"Loaded {len(self._facts)} Zamenhof facts.")
