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
  ACTION_HOLD  — FC: repeat def   | MEDIA: read info via TTS, then resume
  MODE:<n>     — switch to mode n

Adaptive queue (MediaMode):
  Tracks play_count and last_played per entry (persisted in JSON).
  Next track is picked by weighted random:
    - Unplayed tracks get highest weight
    - Tracks not heard recently score higher
    - Manual skip-back never affects weights
  After every session the JSON is saved with updated stats.
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

_signal_queue: queue.Queue = queue.Queue()
_speaking = False


def _speak(text: str, lang: str = "en"):
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

def load_metadata(json_path: Path) -> list:
    """Load media JSON list. Returns [] on error."""
    if not json_path.exists():
        print(f"[META] No metadata file at {json_path}.")
        return []
    try:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[META] Failed to parse {json_path}: {exc}")
        return []


def save_metadata(json_path: Path, entries: list):
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[META] Failed to save {json_path}: {exc}")


def build_info_speech(entry: dict) -> str:
    parts = []
    title  = entry.get("title")
    author = entry.get("author") or entry.get("artist")
    year   = entry.get("year")
    origin = entry.get("origin")
    genre  = entry.get("genre")
    themes = entry.get("themes")
    desc   = entry.get("description")

    if title:  parts.append(f"Title: {title}.")
    if author: parts.append(f"By {author}.")
    if year:   parts.append(f"Year: {year}.")
    if origin: parts.append(f"Origin: {origin}.")
    if genre:  parts.append(f"Genre: {genre}.")
    if themes: parts.append(f"Themes: {', '.join(themes)}.")
    if desc:   parts.append(desc)

    return "  ".join(parts) if parts else "No information available."


# ============================================================
# ADAPTIVE QUEUE
# ============================================================

def _compute_weight(entry: dict, now: datetime) -> float:
    """
    Higher weight = more likely to be picked next.

    Factors:
      - Never played:          weight 10.0  (strong preference for new content)
      - play_count:            weight decreases with each play
      - last_played recency:   tracks not heard for >7 days get a boost
      - rating (1-5 or null):  bonus/penalty; null = neutral
    """
    play_count = entry.get("play_count", 0)
    last_played_str = entry.get("last_played")
    rating = entry.get("rating")  # 1–5 or null

    if play_count == 0:
        return 10.0

    # Base weight: decays with play count, floor at 1.0
    base = max(1.0, 5.0 / play_count)

    # Recency bonus: hours since last play, capped at 7 days
    if last_played_str:
        try:
            last_played = datetime.fromisoformat(last_played_str)
            hours_ago = (now - last_played).total_seconds() / 3600
            recency_bonus = min(hours_ago / 24.0, 7.0)  # max bonus at 7 days
        except Exception:
            recency_bonus = 3.5
    else:
        recency_bonus = 7.0

    # Rating multiplier
    if rating is not None:
        rating_mult = 0.5 + (rating - 1) * 0.25  # 1→0.5, 3→1.0, 5→1.5
    else:
        rating_mult = 1.0

    return (base + recency_bonus * 0.3) * rating_mult


def pick_next_adaptive(entries: list, current_index: int) -> int:
    """
    Weighted random selection excluding current track.
    Returns the index of the chosen entry.
    """
    now = datetime.now()
    n = len(entries)
    if n == 0:
        return 0
    if n == 1:
        return 0

    weights = []
    for i, e in enumerate(entries):
        if i == current_index:
            weights.append(0.0)   # never pick the same track again immediately
        else:
            weights.append(_compute_weight(e, now))

    total = sum(weights)
    if total == 0:
        # fallback: pick any track except current
        candidates = [i for i in range(n) if i != current_index]
        return random.choice(candidates)

    r = random.uniform(0, total)
    cumulative = 0.0
    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return i

    return (current_index + 1) % n  # safety fallback


# ============================================================
# SM-2
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
        _speak(word, lang="pl")

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
            self.shown_definition = True
            self._speak_definition()
        self._next()

    def on_action_hold(self):
        self.shown_definition = True
        self._speak_definition()


# ============================================================
# MEDIA MODE  (poems + music — shared logic, adaptive queue)
# ============================================================

class MediaMode(Mode):

    def __init__(self, directory: Path, name: str, json_filename: str):
        self.directory    = directory
        self.name         = name
        self.json_path    = directory / json_filename
        self.entries:     list = []
        self.index:       int  = 0
        self.playing:     bool = False
        self.paused:      bool = False

    def on_enter(self):
        raw_entries = load_metadata(self.json_path)

        # Build lookup by filename for quick access
        meta_by_filename = {e["filename"]: e for e in raw_entries if "filename" in e}

        files = sorted(self.directory.glob("*.mp3"))
        known = set(meta_by_filename.keys())
        orphans = [f for f in files if f.name not in known]

        valid: list[dict] = []
        for e in raw_entries:
            path = self.directory / e["filename"]
            if path.exists():
                # Ensure adaptive fields exist
                e.setdefault("play_count", 0)
                e.setdefault("last_played", None)
                e.setdefault("rating", None)
                valid.append(e)
            else:
                print(f"[{self.name}] '{e['filename']}' in JSON but MP3 missing — skipped.")

        for f in orphans:
            print(f"[{self.name}] '{f.name}' has no JSON entry — added without metadata.")
            valid.append({
                "id": None, "filename": f.name,
                "play_count": 0, "last_played": None, "rating": None
            })

        self.entries = valid
        self.index   = 0
        self.playing = False
        self.paused  = False

        if not self.entries:
            print(f"[{self.name}] No playable files in {self.directory}.")
            return

        print(f"[{self.name}] {len(self.entries)} track(s) ready.")
        self._play_current()

    # ---- persistence ----

    def _save(self):
        # Only save entries that have JSON metadata (have an "id" key)
        to_save = [e for e in self.entries if e.get("id") is not None]
        save_metadata(self.json_path, to_save)

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

        # Update play stats
        entry["play_count"] = entry.get("play_count", 0) + 1
        entry["last_played"] = datetime.now().isoformat()
        self._save()

        print(f"[{self.name}] ({self.index + 1}/{len(self.entries)}) {label}  "
              f"[played {entry['play_count']}x]")
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
        """Skip forward — adaptive pick."""
        if not self.entries:
            return
        self._stop()
        self.index = pick_next_adaptive(self.entries, self.index)
        self._play_current()

    def on_no(self):
        """Skip backward — simple previous, no weight effect."""
        if not self.entries:
            return
        self._stop()
        self.index = (self.index - 1) % len(self.entries)
        self._play_current()

    def on_action_hold(self):
        """Pause, read metadata aloud, resume."""
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

    # ---- auto-advance (adaptive) ----

    def tick(self):
        if self.playing and not self.paused and pygame.mixer.get_init():
            if not pygame.mixer.music.get_busy():
                print(f"[{self.name}] Track ended — adaptive next.")
                self._stop()
                self.index = pick_next_adaptive(self.entries, self.index)
                self._play_current()


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
        self._started    = False

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
    for line in stdout:
        line = line.strip()
        if line:
            q.put(line)
    q.put(None)


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

        reader = threading.Thread(
            target=_hub_reader,
            args=(process.stdout, _signal_queue),
            daemon=True
        )
        reader.start()

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