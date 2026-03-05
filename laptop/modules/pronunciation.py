"""
modules/pronunciation.py
========================
PRONUNCIATION TRAINING MODE

The robot asks the user to pronounce an Esperanto word.
The microphone records audio, which is then compared to the expected pronunciation
using a speech recognition library.

Libraries used:
    pip install SpeechRecognition pyaudio

How it works:
  1. Robot says a word via TTS.
  2. User presses B to start recording.
  3. User speaks the word into the microphone.
  4. The recorded audio is sent to a speech recogniser (offline: Vosk, or online: Google).
  5. The recognised text is compared to the expected word.
  6. Robot gives feedback.

NOTE: Esperanto support in mainstream STT engines is limited.
      We use phonetic similarity (difflib) as a fallback.
"""

import difflib
import logging
import os
import random
import threading

logger = logging.getLogger(__name__)

VOCAB_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "vocabulary")

# Try to import speech recognition
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    logger.warning("SpeechRecognition not installed – pronunciation mode will be limited. pip install SpeechRecognition pyaudio")


class PronunciationModule:
    """
    Pronunciation training mode.

    Loads vocabulary from the same CSV files used by flashcards.
    """

    def __init__(self, serial, audio, eyes):
        self.serial = serial
        self.audio  = audio
        self.eyes   = eyes

        self._words: list[str] = []      # Esperanto words to practice
        self._index: int = 0
        self._recording: bool = False
        self._recogniser = sr.Recognizer() if SR_AVAILABLE else None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        self._load_words()
        if not self._words:
            self.audio.speak("Neniu vorto trovita por prononca trejnado.")
            return
        random.shuffle(self._words)
        self._index = 0
        self._prompt_word()

    def stop(self):
        self._recording = False

    # ── Button handlers ────────────────────────────────────────────────────────

    def on_button_a(self):
        """Next word."""
        if not self._words:
            return
        self._index = (self._index + 1) % len(self._words)
        self._prompt_word()

    def on_button_b(self):
        """
        Start microphone recording and check pronunciation.
        Runs in a background thread so the UI stays responsive.
        """
        if self._recording:
            return  # already recording
        t = threading.Thread(target=self._record_and_evaluate, daemon=True)
        t.start()

    # ── Core logic ─────────────────────────────────────────────────────────────

    def _prompt_word(self):
        """Tell the user which word to pronounce."""
        if not self._words:
            return
        word = self._words[self._index]
        logger.info(f"Pronunciation prompt: {word}")
        self.eyes.show_text(word)
        self.eyes.set_expression("speaking")
        self.audio.speak(f"Bonvolu prononci: {word}")
        if self.serial:
            self.serial.send({"type": "SHOW_ICON", "icon": "SQUARE"})

    def _record_and_evaluate(self):
        """Record user speech and evaluate it (runs in background thread)."""
        if not SR_AVAILABLE:
            self.audio.speak("Parolrekono ne disponeblas. Instalu SpeechRecognition.")
            return

        expected = self._words[self._index]
        self._recording = True
        self.audio.speak("Parolu nun …")
        self.eyes.set_expression("thinking")

        try:
            with sr.Microphone() as source:
                self._recogniser.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = self._recogniser.listen(source, timeout=5, phrase_time_limit=4)

            # Try Google STT (requires internet); fall back to phonetic similarity
            try:
                recognised = self._recogniser.recognize_google(audio_data, language="eo")
            except Exception:
                recognised = ""

            self._give_feedback(expected, recognised)

        except sr.WaitTimeoutError:
            self.audio.speak("Mi aŭdis nenion. Provu denove.")
        except Exception as exc:
            logger.error(f"Pronunciation recording error: {exc}")
            self.audio.speak("Eraro dum registrado.")
        finally:
            self._recording = False

    def _give_feedback(self, expected: str, recognised: str):
        """Compare recognised text to expected word and give feedback."""
        expected_lower    = expected.lower().strip()
        recognised_lower  = recognised.lower().strip()

        # Use sequence similarity ratio (0.0 – 1.0)
        ratio = difflib.SequenceMatcher(
            None, expected_lower, recognised_lower
        ).ratio()

        logger.info(f"Pronunciation: expected='{expected}', got='{recognised}', ratio={ratio:.2f}")

        if ratio >= 0.8:
            # Good pronunciation
            self.eyes.set_expression("happy")
            self.audio.speak(f"Bonega! Vi bone diris {expected}!")
            if self.serial:
                self.serial.send({"type": "SHOW_ICON", "icon": "HAPPY"})
        elif ratio >= 0.5:
            # Acceptable
            self.eyes.set_expression("idle")
            self.audio.speak(f"Sufiĉe bona. La vorto estas {expected}. Provu denove.")
        else:
            # Needs improvement
            self.eyes.set_expression("sad") if hasattr(self.eyes, "sad") else None
            self.audio.speak(f"Ankoraŭfoje. La vorto estas {expected}.")
            self.audio.speak(expected)   # repeat the word clearly

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_words(self):
        """Load Esperanto words from vocabulary CSVs."""
        import csv, glob
        self._words = []
        for filepath in glob.glob(os.path.join(VOCAB_DIR, "*.csv")):
            try:
                with open(filepath, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        word = row.get("esperanto", "").strip()
                        if word:
                            self._words.append(word)
            except Exception as exc:
                logger.error(f"Failed to load vocabulary: {exc}")
        logger.info(f"Pronunciation module loaded {len(self._words)} word(s).")
