"""
WRO2026 — Esperanto Flashcard Robot
computer.py — main PC logic

Modes:
  0 — FLASHCARDS  (SM-2 spaced repetition + gTTS)
  1 — POEMS       (MP3 playback, metadata from poems/poems.json)
  2 — MUSIC       (MP3 playback, metadata from music/music.json)

Hub signals:
  YES          — FC: correct      | MEDIA: skip forward
  NO           — FC: wrong        | MEDIA: skip backward
  ACTION       — FC: definition   | MEDIA: pause / resume
  ACTION_HOLD  — FC: definition   | MEDIA: read info via TTS, then resume
  MODE:<n>     — switch to mode n (left button hold on hub)
"""

import subprocess
import json
import os
import sys
import random
import tempfile
import queue
import threading
from datetime import datetime, timedelta
from pathlib import Path

from gtts import gTTS
import pygame

# ============================================================
# PATHS
# ============================================================

BASE_DIR       = Path(__file__).parent
ASSETS_DIR     = BASE_DIR / "assets"
FLASHCARDS_DIR = ASSETS_DIR / "flashcards"
POEMS_DIR      = ASSETS_DIR / "poems"
MUSIC_DIR      = ASSETS_DIR / "music"
WORDS_FILE     = FLASHCARDS_DIR / "wordlist.json"

PYTHON = sys.executable

# ============================================================
# AUDIO HELPERS
# ============================================================

def _ensure_mixer():
    if not pygame.mixer.get_init():
        pygame.mixer.init()

# Kolejka sygnałów z huba — wypełniana przez wątek czytający stdout
_signal_queue: queue.Queue = queue.Queue()
_speaking = False   # czy TTS aktualnie gra


def _speak(text: str, lang: str = "en"):
    """
    Synthesize via gTTS and play — ale przerywalny sygnałami z huba.
    Podczas odtwarzania główna pętla może wrzucić sygnał do kolejki
    który przerwie TTS (YES/NO/ACTION/MODE).
    """
    global _speaking
    tts = gTTS(text=text, lang=lang)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        tmp = f.name
    tts.save(tmp)
    _ensure_mixer()
    pygame.mixer.music.load(tmp)
    pygame.mixer.music.play()
    _speaking = True
    try:
        while pygame.mixer.music.get_busy():
            pygame.time.wait(50)
            # Sprawdź czy przyszedł sygnał przerywający
            if not _signal_queue.empty():
                pygame.mixer.music.stop()
                break
    finally:
        _speaking = False
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        try:
            os.unlink(tmp)
        except Exception:
            pass


# ============================================================
# METADATA HELPERS
# ============================================================

def load_metadata(json_path: Path) -> dict:
    """
    Load media JSON and return a dict keyed by filename.
    Returns {} silently if file is missing or malformed.
    """
    if not json_path.exists():
        print(f"[META] No metadata file at {json_path} — continuing without it.")
        return {}
    try:
        with open(json_path, encoding="utf-8") as f:
            entries = json.load(f)
        return {e["filename"]: e for e in entries if "filename" in e}
    except Exception as exc:
        print(f"[META] Failed to parse {json_path}: {exc}")
        return {}


def build_info_speech(entry: dict) -> str:
    """
    Build a TTS-friendly info sentence from a metadata entry.
    Only includes fields that are present, non-null, and non-empty.
    Everything in English for consistency.
    """
    parts = []

    title  = entry.get("title")
    author = entry.get("author") or entry.get("artist")
    year   = entry.get("year")
    origin = entry.get("origin")
    lang   = entry.get("language")
    genre  = entry.get("genre")
    themes = entry.get("themes")
    desc   = entry.get("description")

    if title:  parts.append(f"Title: {title}.")
    if author: parts.append(f"By {author}.")
    if year:   parts.append(f"Year: {year}.")
    if origin: parts.append(f"Origin: {origin}.")
    if lang:   parts.append(f"Language: {lang}.")
    if genre:  parts.append(f"Genre: {genre}.")
    if themes: parts.append(f"Themes: {', '.join(themes)}.")
    if desc:   parts.append(desc)

    return "  ".join(parts) if parts else "No information available for this track."

# ============================================================
# SM-2  (from Fiszki v5 by PantoYT)
# ============================================================

def sr_init(word: dict) -> dict:
    if "sr_ease" not in word:
        word["sr_ease"]        = 2.5
        word["sr_interval"]    = 1
        word["sr_repetitions"] = 0
        word["next_review"]    = datetime.now().isoformat()
    return word


def sr_update(word: dict, is_correct: bool) -> dict:
    sr_init(word)
    quality  = 4 if is_correct else 2
    ease     = word["sr_ease"]
    interval = word["sr_interval"]
    reps     = word["sr_repetitions"]

    new_ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

    if quality < 3:
        new_reps, new_interval = 0, 1
    else:
        new_reps = reps + 1
        if new_reps == 1:   new_interval = 1
        elif new_reps == 2: new_interval = 3
        else:               new_interval = int(interval * new_ease)

    word["sr_ease"]        = new_ease
    word["sr_interval"]    = new_interval
    word["sr_repetitions"] = new_reps
    word["next_review"]    = (datetime.now() + timedelta(minutes=new_interval)).isoformat()
    key = "correct_count" if is_correct else "wrong_count"
    word[key] = word.get(key, 0) + 1
    return word


def pick_next_word(words: list) -> dict:
    now = datetime.now()
    due = [w for w in words if datetime.fromisoformat(sr_init(w)["next_review"]) <= now]
    if due:
        return random.choice(due)
    not_started = [w for w in words if w.get("sr_repetitions", 0) == 0]
    if not_started:
        return random.choice(not_started)
    return min(words, key=lambda w: w.get("next_review", ""))

# ============================================================
# BASE MODE
# ============================================================

class Mode:
    name = "BASE"
    def on_enter(self):       pass
    def on_yes(self):         pass
    def on_no(self):          pass
    def on_action(self):      pass
    def on_action_hold(self): pass
    def tick(self):           pass

# ============================================================
# FLASHCARDS MODE
# ============================================================

class FlashcardsMode(Mode):
    name = "FLASHCARDS"

    def __init__(self):
        self.words:   list = []
        self.current: dict = {}
        self.shown_definition = False

    def on_enter(self):
        with open(WORDS_FILE, encoding="utf-8") as f:
            self.words = json.load(f)
        print("[FC] Wordlist loaded.")
        self._next()

    def _save(self):
        with open(WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.words, f, ensure_ascii=False, indent=2)

    def _next(self):
        self.current = pick_next_word(self.words)
        self.shown_definition = False
        word = self.current["word"]
        print(f"[FC] Word: {word}")
        _speak(word, lang="pl")  # gTTS nie wspiera "eo"; pl jest fonetycznie najbliższe

    def _speak_definition(self):
        translation = self.current.get("translation", "")
        parts = translation.split(" / ")
        en = parts[0].strip() if parts else self.current.get("definition", "")
        pl = parts[1].strip() if len(parts) > 1 else ""
        print(f"[FC] Definition: {en} | {pl}")
        if en: _speak(en, lang="en")
        if pl: _speak(pl, lang="pl")

    def on_yes(self):
        sr_update(self.current, True)
        self._save()
        self._next()

    def on_no(self):
        sr_update(self.current, False)
        self._save()
        if not self.shown_definition:
            self._speak_definition()
        self._next()

    def on_action(self):
        self._speak_definition()
        self.shown_definition = True

    def on_action_hold(self):
        self.on_action()

# ============================================================
# MEDIA MODE  (poems & music)
# ============================================================

class MediaMode(Mode):
    """
    Plays MP3s from a directory using a JSON file as the master list.

    Order: sorted by 'order' field in JSON, then by 'id'.
    Orphan MP3s (no JSON entry) are appended alphabetically at the end.
    Missing MP3s referenced in JSON are skipped with a console warning.

    Controls:
      YES          — skip forward
      NO           — skip backward
      ACTION       — pause / resume
      ACTION_HOLD  — pause, read track info via TTS, resume
    """

    def __init__(self, directory: Path, mode_name: str, meta_filename: str):
        self.directory     = directory
        self.name          = mode_name
        self.meta_filename = meta_filename
        self.entries: list[dict] = []
        self.index  : int  = 0
        self.playing: bool = False
        self.paused : bool = False

    # ---- setup ----

    def on_enter(self):
        meta  = load_metadata(self.directory / self.meta_filename)
        files = sorted(self.directory.glob("*.mp3"))

        # JSON entries sorted by optional 'order', then 'id'
        json_entries = sorted(
            meta.values(),
            key=lambda e: (e.get("order", 9999), e.get("id", ""))
        )

        known = {e["filename"] for e in json_entries}
        orphans = [f for f in files if f.name not in known]

        valid: list[dict] = []
        for entry in json_entries:
            if (self.directory / entry["filename"]).exists():
                valid.append(entry)
            else:
                print(f"[{self.name}] '{entry['filename']}' listed in JSON but MP3 not found — skipped.")

        for f in orphans:
            print(f"[{self.name}] '{f.name}' has no JSON entry — added without metadata.")
            valid.append({"id": None, "filename": f.name})

        self.entries = valid
        self.index   = 0
        self.paused  = False

        if not self.entries:
            print(f"[{self.name}] No playable files found in {self.directory}.")
            return

        print(f"[{self.name}] {len(self.entries)} track(s) ready.")
        self._play_current()

    # ---- playback ----

    def _current_path(self) -> Path | None:
        if not self.entries:
            return None
        return self.directory / self.entries[self.index]["filename"]

    def _play_current(self):
        path = self._current_path()
        if not path:
            return
        entry = self.entries[self.index]
        label = entry.get("title") or path.stem
        print(f"[{self.name}] ({self.index + 1}/{len(self.entries)}) {label}")
        _ensure_mixer()
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.play()
        self.playing = True
        self.paused  = False

    def _stop(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
        self.playing = False
        self.paused  = False

    # ---- controls ----

    def on_yes(self):
        if not self.entries:
            return
        self._stop()
        self.index = (self.index + 1) % len(self.entries)
        self._play_current()

    def on_no(self):
        if not self.entries:
            return
        self._stop()
        self.index = (self.index - 1) % len(self.entries)
        self._play_current()

    def on_action(self):
        if not pygame.mixer.get_init():
            return
        if self.playing and not self.paused:
            pygame.mixer.music.pause()
            self.paused = True
            print(f"[{self.name}] Paused.")
        else:
            pygame.mixer.music.unpause()
            self.paused = False
            print(f"[{self.name}] Resumed.")

    def on_action_hold(self):
        """Pause music, read metadata aloud in English, then resume."""
        was_playing = self.playing and not self.paused
        if was_playing:
            pygame.mixer.music.pause()

        entry = self.entries[self.index] if self.entries else {}
        info  = build_info_speech(entry)
        print(f"[{self.name}] INFO: {info}")
        _speak(info, lang="en")

        if was_playing:
            pygame.mixer.music.unpause()
            self.paused = False

    # ---- auto-advance ----

    def tick(self):
        if self.playing and not self.paused and pygame.mixer.get_init():
            if not pygame.mixer.music.get_busy():
                print(f"[{self.name}] Track ended — auto-advancing.")
                self.on_yes()

# ============================================================
# MODE MANAGER
# ============================================================

class ModeManager:
    def __init__(self):
        self.modes: list[Mode] = [
            FlashcardsMode(),
            MediaMode(POEMS_DIR, "POEMS", "poems.json"),
            MediaMode(MUSIC_DIR, "MUSIC", "music.json"),
        ]
        self.current_idx = 0
        self._started    = False   # czy jakikolwiek tryb już wystartował

    @property
    def current(self) -> Mode:
        return self.modes[self.current_idx]

    def switch_to(self, idx: int):
        idx = idx % len(self.modes)
        if idx == self.current_idx and self._started:
            return
        old = self.current.name
        if self._started and hasattr(self.current, "_stop"):
            self.current._stop()
        self.current_idx = idx
        self._started    = True
        print(f"[MGR] {old} → {self.current.name}")
        self.current.on_enter()

    def start(self):
        self.current.on_enter()

    def handle(self, signal: str):
        m = self.current
        if   signal == "YES":          m.on_yes()
        elif signal == "NO":           m.on_no()
        elif signal == "ACTION":       m.on_action()
        elif signal == "ACTION_HOLD":  m.on_action_hold()
        elif signal.startswith("MODE:"):
            try:
                self.switch_to(int(signal.split(":")[1]))
            except (ValueError, IndexError):
                print(f"[MGR] Bad MODE signal: {signal!r}")
        else:
            print(f"[MGR] Unknown signal: {signal!r}")

    def tick(self):
        self.current.tick()

# ============================================================
# MAIN
# ============================================================

def _hub_reader(stdout, q: queue.Queue):
    """Wątek czytający stdout huba i wrzucający linie do kolejki."""
    for line in stdout:
        line = line.strip()
        if line:
            q.put(line)
    q.put(None)   # sentinel — koniec połączenia


def main():
    os.chdir(BASE_DIR)
    pygame.init()
    import time

    manager = ModeManager()

    while True:
        print("Starting hub connection... (Ctrl+C to quit)")
        process = subprocess.Popen(
            [PYTHON, "-m", "pybricksdev", "run", "ble", "--wait", "hub.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        # Uruchom wątek czytający
        reader = threading.Thread(
            target=_hub_reader,
            args=(process.stdout, _signal_queue),
            daemon=True
        )
        reader.start()

        # Czekaj na READY — czytaj z kolejki
        connected = False
        while True:
            try:
                line = _signal_queue.get(timeout=30)
            except queue.Empty:
                print("[ERR] Timeout waiting for hub — retrying...")
                break
            if line is None:
                break
            print(f"[hub] {line}")
            if line == "READY":
                connected = True
                break

        if not connected:
            print("[ERR] Hub not ready — retrying in 3s...")
            process.terminate()
            time.sleep(3)
            continue

        print("Waiting for mode selection on hub...")

        # Główna pętla — nieblokująca, przetwarza kolejkę
        while True:
            try:
                line = _signal_queue.get(timeout=0.05)
            except queue.Empty:
                manager.tick()
                continue

            if line is None:
                print("[ERR] Hub disconnected — retrying in 3s...")
                break

            if any(s in line for s in ("SystemExit", "Traceback", "program was")):
                print(f"[hub-sys] {line}")
                break

            print(f"[hub] {line}")
            manager.handle(line)
            manager.tick()

        process.terminate()
        time.sleep(3)


if __name__ == "__main__":
    main()