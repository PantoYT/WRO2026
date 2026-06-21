"""
WRO2026 — Esperanto Flashcard Robot
computer.py — main PC logic (English-only source)

Modes:
  0 — FLASHCARDS    (SM-2 spaced repetition + gTTS)
  1 — POEMS         (MP3 playback, metadata from poems/poems.json)
  2 — MUSIC         (MP3 playback, metadata from music/music.json)
  3 — CONVERSATION  (Whisper STT + Groq LLM + gTTS, Esperanto dialogue)
  4 — ATTRACT       (Showcase mode — activates on wake, invites people to interact)
  5 — A0 LESSON     (Scripted A0 teaching mode)

Hub signals:
  YES          — FC: correct      | MEDIA: skip forward  | CONV: push-to-talk | ATTRACT: instructions
  NO           — FC: wrong        | MEDIA: skip backward | CONV: cancel turn   | ATTRACT: instructions
  ACTION_HOLD  — FC: repeat def   | MEDIA: read info     | CONV: change difficulty
  MODE:<n>     — switch to mode n
  SLEEP        — hub entering sleep
  WAKE         — hub detected presence → enters ATTRACT
  ATTRACT_ENTER — hub confirmed attract mode active
  ATTRACT_LOST  — nobody in range for 30s → going back to sleep
  ATTRACT_EXIT  — button pressed in attract → hub opening menu

Sleep/wake:
  Hub monitors distance sensor (Port A) with scanning motor (Port B).
  After inactivity timeout, sends SLEEP. Wakes on distance < 200cm.
  On wake always enters ATTRACT mode first.

TUI behaviour:
  The terminal TUI is PASSIVE — it locks to whatever mode the hub reports via MODE:<n>.
  There is NO way to exit a sub-TUI from the keyboard; only a new MODE: signal
  (from the hub) switches the active sub-TUI.
  Each sub-TUI exposes all controls relevant to its mode.
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import subprocess
import json
import sys
import random
import tempfile
import queue
import threading
import time
import math
import re
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
from bleak import BleakScanner, BleakClient

from gtts import gTTS
import pygame
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import numpy as np
import sounddevice as sd


# ============================================================
# UI LANGUAGE SWITCH
# ============================================================

# ============================================================
# UI LANGUAGE SWITCH
# ============================================================

UI_LANG: str = "pl"          # ← ZMIENIONE NA POLSKI

def _ui(en: str, pl: str) -> str:
    return pl if UI_LANG == "pl" else en

def _speak_ui(en: str, pl: str):
    """Mówi po aktualnym języku"""
    if UI_LANG == "pl":
        _speak(pl, lang="pl")
    else:
        _speak(en, lang="en")


def set_language(lang: str):
    global UI_LANG
    lang = str(lang).lower().strip()[:2]
    if lang == "pl":
        UI_LANG = "pl"
        print("Język zmieniony na POLSKI")
        _speak("Język zmieniony na polski.", lang="pl")
    elif lang in ("en", "ang"):
        UI_LANG = "en"
        print("Language changed to ENGLISH")
        _speak("Language changed to English.", lang="en")


# ============================================================
# PATHS
# ============================================================

BASE_DIR       = Path(__file__).parent
ASSETS_DIR     = BASE_DIR / "assets"
FLASHCARDS_DIR = ASSETS_DIR / "flashcards"
POEMS_DIR      = ASSETS_DIR / "poems"
MUSIC_DIR      = ASSETS_DIR / "music"
WORDS_FILE     = FLASHCARDS_DIR / "wordlist.json"
CONFIG_FILE    = BASE_DIR / "config.json"

PYTHON = sys.executable
HUB_PY_FILE = BASE_DIR / "hub.py"

HUB_NAME = "Espero-bot"

# --- Pybricks BLE protocol (Pybricks Profile v1.3.0+, see pybricks_docs/) ---
# One characteristic carries both directions:
#   PC -> hub : write  [command_byte, payload...]
#   hub -> PC : notify [event_byte, payload...]
PYBRICKS_CMD_UUID  = "c5f50002-8280-46da-89f4-6d8051e4aeef"  # command/event
PYBRICKS_CAP_UUID  = "c5f50003-8280-46da-89f4-6d8051e4aeef"  # hub capabilities
CMD_START_PROGRAM  = 0x01  # start the stored user program
CMD_WRITE_STDIN    = 0x06  # payload goes to the hub's usys.stdin
EVT_WRITE_STDOUT   = 0x01  # payload is what the hub printed to stdout

# Legacy Nordic UART Service (Pybricks firmware < 3.3 only)
NUS_RX_UUID       = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_UUID       = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

# ============================================================
# CONFIG
# ============================================================

_DEFAULT_CONFIG = {
    "groq_api_key":          "",
    "groq_model":            "llama-3.3-70b-versatile",
    "whisper_model":         "base",
    "whisper_device":        "cpu",
    "audio_activity_db":     -30,
    "audio_sample_rate":     16000,
    "audio_record_seconds":  6,
    "inactivity_timeout_s":  180,
    "conv_history_turns":    8,
    "speaker_volume":        20,
}

def _load_config() -> dict:
    cfg = dict(_DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[CFG] Failed to load config.json: {e}")
    if os.environ.get("GROQ_API_KEY"):
        cfg["groq_api_key"] = os.environ["GROQ_API_KEY"]
    return cfg

CFG = _load_config()

# ============================================================
# ACTIVITY TRACKER
# ============================================================

class ActivityTracker:
    def __init__(self):
        self._last_activity = time.monotonic()
        self._lock = threading.Lock()
        self._sleeping = False

    def poke(self):
        with self._lock:
            self._last_activity = time.monotonic()
            self._sleeping = False

    def seconds_since(self) -> float:
        with self._lock:
            return time.monotonic() - self._last_activity

    def is_sleeping(self) -> bool:
        with self._lock:
            return self._sleeping

    def set_sleeping(self, val: bool):
        with self._lock:
            self._sleeping = val

ACTIVITY = ActivityTracker()

# ============================================================
# HUB FLASHING
# ============================================================

def _flash_hub_py():
    if not HUB_PY_FILE.exists():
        print(f"[FLASH] Error: {HUB_PY_FILE} not found")
        return False
    print(f"[FLASH] Uploading {HUB_PY_FILE.name} to '{HUB_NAME}'...")
    print(f"[FLASH] Make sure the hub is on and NOT already running a program.")
    try:
        result = subprocess.run(
            [PYTHON, "-m", "pybricksdev", "run", "ble",
             "--name", HUB_NAME,
             "--no-start",
             str(HUB_PY_FILE)],
            timeout=60,
            text=True,
        )
        if result.returncode == 0:
            print("[FLASH] ✓ hub.py uploaded.")
            return True
        else:
            print(f"[FLASH] ✗ Upload failed (code {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        print("[FLASH] ✗ Timed out (60s)")
        return False
    except Exception as e:
        print(f"[FLASH] ✗ Error: {e}")
        return False

# ============================================================
# MIC ACTIVITY MONITOR
# ============================================================

_mic_monitor_running = False

def _mic_rms_db(data: np.ndarray) -> float:
    rms = np.sqrt(np.mean(data.astype(np.float32) ** 2))
    if rms < 1e-9:
        return -96.0
    return 20 * math.log10(rms / 32768.0)

def _start_mic_monitor():
    global _mic_monitor_running
    if _mic_monitor_running:
        return
    _mic_monitor_running = True
    threshold_db = CFG["audio_activity_db"]
    rate         = CFG["audio_sample_rate"]
    chunk        = int(rate * 0.2)

    def _loop():
        try:
            with sd.InputStream(samplerate=rate, channels=1,
                                dtype="int16", blocksize=chunk) as stream:
                while _mic_monitor_running:
                    data, _ = stream.read(chunk)
                    if _mic_rms_db(data) > threshold_db:
                        ACTIVITY.poke()
        except Exception as e:
            print(f"[MIC] Monitor error: {e}")

    threading.Thread(target=_loop, daemon=True).start()

# ============================================================
# AUDIO HELPERS
# ============================================================

def _ensure_mixer():
    if not pygame.mixer.get_init():
        pygame.mixer.init()

_signal_queue: queue.Queue = queue.Queue()

# PC -> hub sender. Set by the BLE thread once connected, None while offline.
# Any part of the program can call hub_send("SIGNAL") — see hub.py
# handle_pc_signal() for the accepted commands.
_hub_send_fn = None

def hub_send(msg: str):
    """Queue a line for the hub's stdin (sent as '<msg>\\n' over BLE)."""
    fn = _hub_send_fn
    if fn is None:
        print(f"[BLE] (hub offline) dropped: {msg!r}")
        return
    try:
        fn(msg)
    except Exception as e:
        print(f"[BLE] hub_send({msg!r}) failed: {e}")

_speaking = False
_speaking_lock = threading.Lock()
_tts_stop_event = threading.Event()


def _request_tts_stop():
    _tts_stop_event.set()
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass


def eo_to_pl_phonetic(text: str) -> str:
    specials = [
        ("ĉ", "\uE000"), ("Ĉ", "\uE001"),
        ("ŝ", "\uE002"), ("Ŝ", "\uE003"),
        ("ĝ", "\uE004"), ("Ĝ", "\uE005"),
        ("ĵ", "\uE006"), ("Ĵ", "\uE007"),
        ("ĥ", "\uE008"), ("Ĥ", "\uE009"),
        ("ŭ", "\uE00A"), ("Ŭ", "\uE00B"),
    ]
    result = text
    for src, ph in specials:
        result = result.replace(src, ph)
    for src, dst in [("io", "ijo"), ("Io", "Ijo"), ("IO", "IJO"),
                     ("ia", "ija"), ("Ia", "Ija"),
                     ("ie", "ije"), ("Ie", "Ije")]:
        result = result.replace(src, dst)
    result = result.replace("qu", "kw").replace("Qu", "Kw").replace("QU", "KW")
    result = result.replace("c", "ts").replace("C", "Ts")
    finals = [
        ("\uE000", "cz"), ("\uE001", "Cz"),
        ("\uE002", "sz"), ("\uE003", "Sz"),
        ("\uE004", "dż"), ("\uE005", "Dż"),
        ("\uE006", "ż"),  ("\uE007", "Ż"),
        ("\uE008", "h"),  ("\uE009", "H"),
        ("\uE00A", "ł"),  ("\uE00B", "Ł"),
    ]
    for ph, dst in finals:
        result = result.replace(ph, dst)
    result = re.sub(r'on\b', 'onn', result)
    result = re.sub(r'an\b', 'ann', result)
    result = re.sub(r'en\b', 'enn', result)
    return result


def _speak(text: str, lang: str = "en"):
    global _speaking
    if _tts_stop_event.is_set():
        return
    if lang == "eo":
        text = eo_to_pl_phonetic(text)
        lang = "pl"

    _EDGE_VOICES = {
        "pl": "pl-PL-MarekNeural",
        "en": "en-GB-RyanNeural",
    }

    tmp = None
    try:
        voice = _EDGE_VOICES.get(lang)
        if voice:
            try:
                import edge_tts as _edge_tts_mod
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                    tmp = f.name

                _edge_exc: list[Exception] = []

                def _run_edge_synth():
                    import asyncio as _aio
                    async def _synth():
                        communicate = _edge_tts_mod.Communicate(text, voice)
                        await communicate.save(tmp)
                    loop = _aio.new_event_loop()
                    try:
                        loop.run_until_complete(_synth())
                    except Exception as e:
                        _edge_exc.append(e)
                    finally:
                        loop.close()

                t = threading.Thread(target=_run_edge_synth, daemon=True)
                t.start()
                t.join(timeout=15)
                if t.is_alive() or _edge_exc:
                    raise Exception(_edge_exc[0] if _edge_exc else "timeout")
            except Exception as e:
                print(f"[TTS] edge-tts failed ({e}), falling back to gTTS")
                tmp = None

        if tmp is None:
            tts = gTTS(text=text, lang=lang)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                tmp = f.name
            tts.save(tmp)

        _ensure_mixer()
        pygame.mixer.music.load(tmp)
        pygame.mixer.music.play()
        with _speaking_lock:
            global _speaking
            _speaking = True
        try:
            while pygame.mixer.music.get_busy():
                pygame.time.wait(50)
                if _tts_stop_event.is_set():
                    pygame.mixer.music.stop()
                    break
        finally:
            with _speaking_lock:
                _speaking = False
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
    except Exception as e:
        print(f"[TTS] Error: {e}")
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except Exception:
                pass


def _speak_eo_with_hint(word: str, pronunciation: str = ""):
    _speak(word, lang="eo")


# ============================================================
# METADATA HELPERS
# ============================================================

def load_metadata(json_path: Path) -> list:
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


def build_info_speech(entry: dict) -> tuple[str, str]:
    parts = []
    if UI_LANG == "pl":
        title  = entry.get("title_pl")  or entry.get("title")
        author = entry.get("author")    or entry.get("artist")
        year   = entry.get("year")
        origin = entry.get("origin")
        genre  = entry.get("genre")
        themes = entry.get("themes_pl") or entry.get("themes")
        desc   = entry.get("description_pl") or entry.get("description")
        if title:  parts.append(f"Tytuł: {title}.")
        if author: parts.append(f"Autor: {author}.")
        if year:   parts.append(f"Rok: {year}.")
        if origin: parts.append(f"Pochodzenie: {origin}.")
        if genre:  parts.append(f"Gatunek: {genre}.")
        if themes: parts.append(f"Tematy: {', '.join(themes)}.")
        if desc:   parts.append(desc)
        text = "  ".join(parts) if parts else "Brak informacji."
        return text, "pl"
    else:
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
        text = "  ".join(parts) if parts else "No information available."
        return text, "en"


# ============================================================
# ADAPTIVE QUEUE
# ============================================================

def _compute_weight(entry: dict, now: datetime) -> float:
    play_count = entry.get("play_count", 0)
    last_played_str = entry.get("last_played")
    rating = entry.get("rating")
    if play_count == 0:
        return 10.0
    base = max(1.0, 5.0 / play_count)
    if last_played_str:
        try:
            last_played = datetime.fromisoformat(last_played_str)
            hours_ago = (now - last_played).total_seconds() / 3600
            recency_bonus = min(hours_ago / 24.0, 7.0)
        except Exception:
            recency_bonus = 3.5
    else:
        recency_bonus = 7.0
    rating_mult = (0.5 + (rating - 1) * 0.25) if rating is not None else 1.0
    return (base + recency_bonus * 0.3) * rating_mult


def pick_next_adaptive(entries: list, current_index: int) -> int:
    now = datetime.now()
    n = len(entries)
    if n <= 1:
        return 0
    weights = [0.0 if i == current_index else _compute_weight(e, now)
               for i, e in enumerate(entries)]
    total = sum(weights)
    if total == 0:
        candidates = [i for i in range(n) if i != current_index]
        return random.choice(candidates)
    r = random.uniform(0, total)
    cumulative = 0.0
    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return i
    return (current_index + 1) % n


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
    def on_sleep(self):       pass
    def on_wake(self):        pass
    def tick(self):           pass


# ============================================================
# FLASHCARDS MODE
# ============================================================

class FlashcardsMode(Mode):
    name = "FLASHCARDS"

    _SESSION_CTAS_EN = [
        ("Great practice! Now listen to some real Esperanto music to hear the language in action. "
         "Open the menu and try Music mode."),
        "Well done! Esperanto has real poets too. Try Poems mode to hear the language come alive.",
        ("Nice session! Want to use these words in a real conversation? "
         "Try Conversation mode — press and hold the left button to open the menu."),
        ("Keep it up! The more you practise, the faster Esperanto becomes natural. "
         "See you next round!"),
    ]

    def __init__(self):
        self.words:   list = []
        self._all_words: list = []
        self.current: dict = {}
        self.shown_definition = False
        self.session_correct: int = 0
        self.session_wrong:   int = 0
        self.active_filter: str | None = None

    def on_enter(self):
        with open(WORDS_FILE, encoding="utf-8") as f:
            self._all_words = json.load(f)
        print("[FC] Wordlist loaded.")
        self.session_correct = 0
        self.session_wrong   = 0
        self._apply_filter()
        self._announce_filter()
        self._next()

    def _apply_filter(self):
        if self.active_filter:
            filtered = [w for w in self._all_words
                        if w.get("unit", "").lower() == self.active_filter.lower()]
            self.words = filtered if filtered else self._all_words
            if not filtered:
                print(f"[FC] Filter '{self.active_filter}' matched 0 words — using all.")
        else:
            self.words = self._all_words

    def _announce_filter(self):
        if self.active_filter:
            count = len(self.words)
            _speak_ui(
                f"Flashcard filter: {self.active_filter}. {count} words.",
                f"Filtr fiszek: {self.active_filter}. {count} słów.",
            )
        else:
            _speak_ui(
                f"Flashcards — {len(self.words)} words ready.",
                f"Fiszki — {len(self.words)} słów gotowych.",
            )

    def set_filter(self, unit: str | None):
        self.active_filter = unit
        print(f"[FC] Filter set to: {unit!r}")

    def _save(self):
        with open(WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._all_words, f, ensure_ascii=False, indent=2)

    def _next(self):
        self.current = pick_next_word(self.words)
        self.shown_definition = False
        word         = self.current["word"]
        unit         = self.current.get("unit", "")
        pronunciation = self.current.get("pronunciation", "")
        print(f"[FC] Word: {word}  [{pronunciation}]  ({unit})" if pronunciation
              else f"[FC] Word: {word}  ({unit})")
        _speak_eo_with_hint(word, pronunciation)

    def _speak_definition(self):
        word          = self.current.get("word", "")
        pronunciation = self.current.get("pronunciation", "")
        translation   = self.current.get("translation", "")
        definition    = self.current.get("definition", "")
        parts = translation.split(" / ")
        en = parts[0].strip() if parts else definition
        pl = parts[1].strip() if len(parts) > 1 else ""
        print(f"[FC] Definition: {en} | {pl}")
        _speak(word, lang="eo")
        if UI_LANG == "pl":
            if pl:
                _speak(f"{word} znaczy: {pl}", lang="pl")
            elif en:
                _speak(f"{word} means: {en}", lang="en")
            if definition and definition.lower() not in (en.lower(), pl.lower()):
                _speak(definition, lang="pl")
        else:
            if en:
                _speak(f"{word} means: {en}", lang="en")
            if pl:
                _speak(pl, lang="pl")
            if definition and definition.lower() not in (en.lower(), pl.lower()):
                _speak(definition, lang="en")

    def on_yes(self):
        ACTIVITY.poke()
        sr_update(self.current, True)
        self._save()
        self.session_correct += 1
        self._next()

    def on_no(self):
        ACTIVITY.poke()
        sr_update(self.current, False)
        self._save()
        self.session_wrong += 1
        if not self.shown_definition:
            self.shown_definition = True
            self._speak_definition()
        self._next()

    def on_action_hold(self):
        ACTIVITY.poke()
        self.shown_definition = True
        self._speak_definition()

    def get_stats(self) -> dict:
        """Return current session and overall stats."""
        total = self.session_correct + self.session_wrong
        due_now = sum(
            1 for w in self.words
            if datetime.fromisoformat(sr_init(w)["next_review"]) <= datetime.now()
        )
        hardest = sorted(self._all_words,
                         key=lambda w: w.get("wrong_count", 0), reverse=True)[:5]
        best    = sorted(self._all_words,
                         key=lambda w: w.get("correct_count", 0), reverse=True)[:5]
        return {
            "session_correct": self.session_correct,
            "session_wrong":   self.session_wrong,
            "session_total":   total,
            "due_now":         due_now,
            "total_words":     len(self.words),
            "hardest":         hardest,
            "best":            best,
            "active_filter":   self.active_filter,
        }

    def _speak_session_summary(self):
        total = self.session_correct + self.session_wrong
        if total == 0:
            return
        summary = f"Podsumowanie sesji: {self.session_correct} poprawnych, {self.session_wrong} błędnych z {total} fiszek."
        cta = random.choice([
            "Świetna sesja! Teraz posłuchaj muzyki esperanto.",
            "Dobra robota! Spróbuj trybu Poezja.",
            "Chcesz rozmawiać? Przejdź do trybu Konwersacja.",
            "Kontynuuj ćwiczenia — idzie Ci świetnie!"
        ])
        print(f"[FC] {summary}")
        _speak(summary, lang="pl")
        _speak(cta, lang="pl")
        self.session_correct = 0
        self.session_wrong   = 0

    def on_sleep(self):
        self._speak_session_summary()


# ============================================================
# MEDIA MODE
# ============================================================

class MediaMode(Mode):

    def __init__(self, directory: Path, name: str, json_filename: str):
        self.directory = directory
        self.name      = name
        self.json_path = directory / json_filename
        self.entries:  list = []
        self.index:    int  = 0
        self.playing:  bool = False
        self.paused:   bool = False

    def _load_entries(self) -> list:
        raw_entries = load_metadata(self.json_path)
        meta_by_filename = {e["filename"]: e for e in raw_entries if "filename" in e}
        files   = sorted(self.directory.glob("*.mp3"))
        known   = set(meta_by_filename.keys())
        orphans = [f for f in files if f.name not in known]
        valid: list[dict] = []
        for e in raw_entries:
            path = self.directory / e["filename"]
            if path.exists():
                e.setdefault("play_count", 0)
                e.setdefault("last_played", None)
                e.setdefault("rating", None)
                valid.append(e)
            else:
                print(f"[{self.name}] '{e['filename']}' in JSON but MP3 missing — skipped.")
        for f in orphans:
            print(f"[{self.name}] '{f.name}' has no JSON entry — added without metadata.")
            valid.append({"id": None, "filename": f.name,
                          "play_count": 0, "last_played": None, "rating": None})
        return valid

    def preload_entries(self):
        if not self.entries:
            self.entries = self._load_entries()
            if self.entries:
                print(f"[{self.name}] preloaded {len(self.entries)} track(s) for Attract.")
            else:
                print(f"[{self.name}] No playable files in {self.directory}.")

    def on_enter(self):
        self.entries = self._load_entries()
        self.index   = 0
        self.playing = False
        self.paused  = False
        if not self.entries:
            print(f"[{self.name}] No playable files in {self.directory}.")
            return
        print(f"[{self.name}] {len(self.entries)} track(s) ready.")
        self._play_current()

    def _save(self):
        to_save = [e for e in self.entries if e.get("id") is not None]
        save_metadata(self.json_path, to_save)

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

    def pause(self):
        if self.playing and not self.paused and pygame.mixer.get_init():
            pygame.mixer.music.pause()
            self.paused = True
            print(f"[{self.name}] Paused.")

    def unpause(self):
        if self.paused and pygame.mixer.get_init():
            pygame.mixer.music.unpause()
            self.paused = False
            print(f"[{self.name}] Resumed.")

    def toggle_pause(self):
        if self.paused:
            self.unpause()
        else:
            self.pause()

    def set_volume(self, vol: float):
        """Set volume 0.0–1.0"""
        vol = max(0.0, min(1.0, vol))
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(vol)
            print(f"[{self.name}] Volume: {int(vol*100)}%")

    def jump_to(self, idx: int):
        if not self.entries:
            print(f"[{self.name}] No entries loaded.")
            return
        self._stop()
        self.index = idx % len(self.entries)
        self._play_current()

    def rate_current(self, stars: int):
        """Rate current track 1–5 stars."""
        if not self.entries:
            return
        stars = max(1, min(5, stars))
        self.entries[self.index]["rating"] = stars
        self._save()
        label = self.entries[self.index].get("title") or self.entries[self.index]["filename"]
        print(f"[{self.name}] Rated '{label}': {'★' * stars}")

    def now_playing(self) -> str:
        if not self.entries or not self.playing:
            return "(nothing playing)"
        e = self.entries[self.index]
        title  = e.get("title") or e["filename"]
        artist = e.get("artist") or e.get("author", "")
        plays  = e.get("play_count", 0)
        rating = ("★" * e["rating"]) if e.get("rating") else ""
        status = "⏸ PAUSED" if self.paused else "▶ PLAYING"
        return (f"{status}  [{self.index+1}/{len(self.entries)}]  "
                f"{title}" + (f"  — {artist}" if artist else "") +
                f"  [{plays}x]" + (f"  {rating}" if rating else ""))

    def on_yes(self):
        ACTIVITY.poke()
        if not self.entries: return
        self._stop()
        self.index = pick_next_adaptive(self.entries, self.index)
        self._play_current()

    def on_no(self):
        ACTIVITY.poke()
        if not self.entries: return
        self._stop()
        self.index = (self.index - 1) % len(self.entries)
        self._play_current()

    def on_action_hold(self):
        ACTIVITY.poke()
        was_playing = self.playing and not self.paused
        music_pos_ms: float = 0.0
        if was_playing and pygame.mixer.get_init():
            music_pos_ms = pygame.mixer.music.get_pos()
            pygame.mixer.music.pause()
        entry = self.entries[self.index] if self.entries else {}
        info_text, info_lang = build_info_speech(entry)
        print(f"[{self.name}] INFO: {info_text}")
        _speak(info_text, lang=info_lang)
        if was_playing:
            path = self._current_path()
            if path:
                try:
                    _ensure_mixer()
                    pygame.mixer.music.load(str(path))
                    seek_s = max(0.0, music_pos_ms / 1000.0)
                    pygame.mixer.music.play(start=seek_s)
                    self.paused = False
                except Exception as e:
                    print(f"[{self.name}] Could not resume after info: {e}")

    def on_sleep(self):
        if self.playing:
            pygame.mixer.music.pause()
            self.paused = True

    def on_wake(self):
        if self.paused:
            pygame.mixer.music.unpause()
            self.paused = False

    def tick(self):
        if self.playing and not self.paused and pygame.mixer.get_init():
            if not pygame.mixer.music.get_busy():
                print(f"[{self.name}] Track ended — adaptive next.")
                self._stop()
                self.index = pick_next_adaptive(self.entries, self.index)
                self._play_current()


# ============================================================
# A0 LESSON MODE
# ============================================================

_A0_LESSONS = [
    {
        "id": "greetings",
        "title_en": "Greetings",       "title_pl": "Powitania",
        "intro": (
            "Welcome to your first Esperanto lesson! "
            "Esperanto has no irregular words — what you see is what you say. "
            "Let's learn greetings.",
            "Witaj na pierwszej lekcji esperanto! "
            "Esperanto nie ma wyjątków — piszesz tak jak słyszysz. "
            "Nauczymy się powitań.",
        ),
        "steps": [
            ("saluton", "SA-lu-ton", "Hello!", "Cześć!"),
            ("saluton", "SA-lu-ton", "Saluton means: Hello.", "Saluton znaczy: Cześć."),
            ("dankon",  "DAN-kon",   "Thank you!", "Dziękuję!"),
            ("dankon",  "DAN-kon",   "Dankon means: Thank you.", "Dankon znaczy: Dziękuję."),
            ("bonvolu", "bon-VO-lu", "Please!", "Proszę!"),
            ("jes",     "yes",       "Yes!", "Tak!"),
            ("ne",      "ne",        "No!", "Nie!"),
            ("bonan matenon", "BO-nan ma-TE-non", "Good morning!", "Dzień dobry!"),
            ("bonan tagon",   "BO-nan TA-gon",    "Good day!", "Dobry dzień!"),
            ("ĝis revido",    "djis re-VI-do",
             "Goodbye — see you again!", "Do widzenia — do następnego razu!"),
        ],
        "outro": (
            "You know the basics! Now go practise in Flashcards mode.",
            "Znasz już podstawy! Ćwicz dalej w trybie Fiszki.",
        ),
        "filter_cta": None,
    },
    {
        "id": "numbers",
        "title_en": "Numbers", "title_pl": "Liczby",
        "intro": (
            "In Esperanto, numbers are completely regular.",
            "W esperanto liczby są całkowicie regularne.",
        ),
        "steps": [
            ("unu",  "U-nu",  "One.",   "Jeden."),
            ("du",   "du",    "Two.",   "Dwa."),
            ("tri",  "tri",   "Three.", "Trzy."),
            ("kvar", "kvar",  "Four.",  "Cztery."),
            ("kvin", "kvin",  "Five.",  "Pięć."),
            ("ses",  "ses",   "Six.",   "Sześć."),
            ("sep",  "sep",   "Seven.", "Siedem."),
            ("ok",   "ok",    "Eight.", "Osiem."),
            ("naŭ",  "naw",   "Nine.",  "Dziewięć."),
            ("dek",  "dek",   "Ten.",   "Dziesięć."),
            ("dek unu", "dek U-nu",
             "Eleven. Just dek plus unu — no irregulars ever!",
             "Jedenaście. Po prostu dek plus unu!"),
        ],
        "outro": (
            "Numbers done! Head to Flashcards — Numbers unit — to drill them.",
            "Liczby zaliczone! Przejdź do Fiszek — filtr Liczby.",
        ),
        "filter_cta": "Numbers",
    },
    {
        "id": "culture",
        "title_en": "Esperanto Culture", "title_pl": "Kultura esperanto",
        "intro": (
            "Esperanto has 130 years of poetry, music, and congresses.",
            "Esperanto ma 130 lat poezji, muzyki i kongresów.",
        ),
        "steps": [
            ("espero",  "es-PE-ro",
             "Hope. The word Esperanto means 'one who hopes'.",
             "Nadzieja. Słowo Esperanto znaczy 'ten, który ma nadzieję'."),
            ("paco",    "PA-tso",    "Peace.",    "Pokój."),
            ("mondo",   "MON-do",    "World.",    "Świat."),
            ("lingvo",  "LING-vo",   "Language.", "Język."),
            ("kulturo", "kul-TU-ro", "Culture.",  "Kultura."),
            ("muziko",  "mu-ZI-ko",  "Music.",    "Muzyka."),
            ("poemo",   "po-E-mo",   "Poem.",     "Wiersz."),
            ("verda stelo", "VER-da STE-lo",
             "The green star — symbol of the Esperanto movement.",
             "Zielona gwiazda — symbol ruchu esperanckiego."),
            ("kongreso", "kon-GRE-so",
             "Congress — Esperanto speakers meet every year at the World Congress.",
             "Kongres — esperantyści spotykają się co roku na Światowym Kongresie."),
            ("zamenhof", "za-MEN-hof",
             "Zamenhof — creator of Esperanto, 1887.",
             "Zamenhof — twórca esperanta, 1887."),
        ],
        "outro": (
            "Beautiful! Try Poems or Music mode from the menu.",
            "Wspaniale! Wypróbuj tryb Poezja lub Muzyka z menu.",
        ),
        "filter_cta": "Culture",
    },
    {
        "id": "technology",
        "title_en": "Robots and Technology", "title_pl": "Roboty i technologia",
        "intro": (
            "You're talking to a robot right now! Let's learn tech words in Esperanto.",
            "Właśnie rozmawiasz z robotem! Nauczymy się esperanckich słów technologicznych.",
        ),
        "steps": [
            ("roboto",      "ro-BO-to",      "Robot!",              "Robot!"),
            ("komputilo",   "kom-pu-TI-lo",  "Computer.",           "Komputer."),
            ("sensilo",     "sen-SI-lo",      "Sensor.",             "Czujnik."),
            ("ekrano",      "ek-RA-no",       "Screen, display.",    "Ekran."),
            ("programi",    "pro-GRA-mi",
             "To program — all verbs end in -i in Esperanto.",
             "Programować — wszystkie bezokoliczniki kończą się na -i."),
            ("datumoj",     "da-TU-moy",      "Data.",               "Dane."),
            ("aŭtomata",    "aw-to-MA-ta",    "Automatic.",          "Automatyczny."),
            ("inteligenta", "in-te-li-GEN-ta","Intelligent.",        "Inteligentny."),
            ("artefarita inteligenteco", "ar-te-fa-RI-ta in-te-li-gen-TE-tso",
             "Artificial intelligence.", "Sztuczna inteligencja."),
            ("inventi",     "in-VEN-ti",
             "To invent. Zamenhof invented Esperanto in 1887.",
             "Wynaleźć. Zamenhof wynalazł esperanto w 1887 roku."),
        ],
        "outro": (
            "Roboto, sensilo, programi — you speak robot Esperanto now!",
            "Roboto, sensilo, programi — mówisz już po esperanto jak robot!",
        ),
        "filter_cta": "Technology",
    },
]


class A0LessonMode(Mode):
    name = "A0_LESSON"

    def __init__(self):
        self.lesson_idx:  int  = 0
        self.step_idx:    int  = 0
        self._lesson:     dict = _A0_LESSONS[0]
        self._in_lesson:  bool = False
        self._done:       bool = False

    def on_enter(self):
        self.lesson_idx = 0
        self.step_idx   = 0
        self._done      = False
        self._start_lesson()

    def _start_lesson(self):
        self._lesson    = _A0_LESSONS[self.lesson_idx % len(_A0_LESSONS)]
        self.step_idx   = 0
        self._in_lesson = True
        self._done      = False
        title = self._lesson["title_pl"] if UI_LANG == "pl" else self._lesson["title_en"]
        print(f"[A0] Lesson: {title}")
        _speak_ui(
            f"Lesson {self.lesson_idx + 1}: {self._lesson['title_en']}.",
            f"Lekcja {self.lesson_idx + 1}: {self._lesson['title_pl']}.",
        )
        intro_en, intro_pl = self._lesson["intro"]
        _speak(intro_pl if UI_LANG == "pl" else intro_en, lang=UI_LANG)
        _speak_ui("Press YES for the next step, NO to repeat.",
                  "Naciśnij TAK żeby przejść dalej, NIE żeby powtórzyć.")
        self._speak_step()

    def _speak_step(self):
        steps = self._lesson["steps"]
        if self.step_idx >= len(steps):
            self._finish_lesson()
            return
        word, pronunciation, meaning_en, meaning_pl = steps[self.step_idx]
        print(f"[A0] Step {self.step_idx + 1}/{len(steps)}: {word}")
        _speak_eo_with_hint(word, pronunciation)
        _speak(meaning_pl if UI_LANG == "pl" else meaning_en, lang=UI_LANG)

    def _finish_lesson(self):
        self._in_lesson = False
        outro_en, outro_pl = self._lesson["outro"]
        _speak(outro_pl if UI_LANG == "pl" else outro_en, lang=UI_LANG)
        filter_unit = self._lesson.get("filter_cta")
        if filter_unit:
            print(f"LESSON_FILTER:{filter_unit}")
        next_idx = self.lesson_idx + 1
        if next_idx < len(_A0_LESSONS):
            next_lesson = _A0_LESSONS[next_idx]
            next_title = next_lesson["title_pl"] if UI_LANG == "pl" else next_lesson["title_en"]
            _speak_ui(
                f"Press YES for the next lesson: {next_title}. Or NO for the menu.",
                f"Naciśnij TAK żeby przejść do: {next_title}. Albo NIE — menu.",
            )
            self._done = True
        else:
            _speak_ui(
                "You've completed all A0 lessons! Press NO for the menu.",
                "Ukończyłeś wszystkie lekcje A0! Naciśnij NIE — menu.",
            )
            self._done = True

    def on_yes(self):
        ACTIVITY.poke()
        if self._done:
            next_idx = self.lesson_idx + 1
            if next_idx < len(_A0_LESSONS):
                self.lesson_idx = next_idx
                self.step_idx   = 0
                self._done      = False
                self._start_lesson()
            else:
                _speak_ui(
                    "All lessons complete! Open the menu to explore other modes.",
                    "Wszystkie lekcje ukończone! Otwórz menu.",
                )
        elif self._in_lesson:
            self.step_idx += 1
            self._speak_step()

    def on_no(self):
        ACTIVITY.poke()
        if self._done:
            print("LESSON_EXIT")
        elif self._in_lesson:
            self._speak_step()

    def on_action_hold(self):
        ACTIVITY.poke()
        title = self._lesson["title_pl"] if UI_LANG == "pl" else self._lesson["title_en"]
        _speak_ui(f"You're in lesson: {title}.", f"Jesteś w lekcji: {title}.")
        intro_en, intro_pl = self._lesson["intro"]
        _speak(intro_pl if UI_LANG == "pl" else intro_en, lang=UI_LANG)

    def on_sleep(self): pass
    def tick(self):     pass

    def get_progress(self) -> str:
        lesson = self._lesson
        title  = lesson["title_pl"] if UI_LANG == "pl" else lesson["title_en"]
        total  = len(lesson["steps"])
        return (f"Lesson {self.lesson_idx+1}/{len(_A0_LESSONS)}: {title}  "
                f"Step {self.step_idx+1}/{total}")


# ============================================================
# CONVERSATION MODE
# ============================================================

_CONV_SYSTEM_PROMPTS = {
    "A1": (
        "Vi estas afabla esperanto-instruisto por komencantoj (nivelo A1). "
        "Uzu nur bazajn vortojn. Skribu mallongajn frazojn (maks. 10 vortoj). "
        "Respondu NUR en Esperanto."
    ),
    "B1": (
        "Vi estas amika Esperanto-parolanto je nivelo B1. "
        "Uzu normalan rapidecon. Respondu NUR en Esperanto."
    ),
    "C1": (
        "Vi estas denaska Esperanto-parolanto kun riĉa vortprovizo. "
        "Uzu idiomojn, humuron, kulturajn referencojn. Respondu NUR en Esperanto."
    ),
}

_DIFFICULTY_LABELS = ["A1", "B1", "C1"]


def _groq_chat(history: list[dict], system: str, api_key: str, model: str) -> str:
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}] + history,
            max_tokens=200,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[CONV] Groq error: {e}")
        try:
            import urllib.request
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "system", "content": system}] + history,
                "max_tokens": 200, "temperature": 0.7,
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "groq-python/0.9.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"].strip()
        except Exception as e2:
            print(f"[CONV] Fallback also failed: {e2}")
            return "Pardonu, eraro okazis."


def _record_audio(seconds: int, sample_rate: int) -> np.ndarray:
    print(f"[CONV] Recording {seconds}s...")
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate,
                   channels=1, dtype="int16")
    sd.wait()
    return audio.flatten()


class ConversationMode(Mode):
    name = "CONVERSATION"

    def __init__(self):
        self.difficulty_idx: int  = 0
        self.history: list[dict]  = []
        self._recording: bool     = False
        self._lock                = threading.Lock()
        self._whisper_model       = None
        self._wav2vec2_model      = None
        self._wav2vec2_processor  = None
        self._pending_media_offer: bool = False

    @property
    def difficulty(self) -> str:
        return _DIFFICULTY_LABELS[self.difficulty_idx]

    @property
    def system_prompt(self) -> str:
        return _CONV_SYSTEM_PROMPTS[self.difficulty]

    def _cycle_difficulty(self):
        self.difficulty_idx = (self.difficulty_idx + 1) % len(_DIFFICULTY_LABELS)
        print(f"[CONV] Difficulty → {self.difficulty}")
        _speak(f"Nivelo {self.difficulty}", lang="eo")

    def _get_whisper(self):
        return None

    def _get_wav2vec2(self):
        if self._wav2vec2_model is None:
            # On Windows, torch's c10.dll can transiently fail to init with
            # WinError 1114 when antivirus is scanning freshly-installed DLLs.
            # Retry a few times — the DLLs warm up and the next attempt succeeds.
            for attempt in range(1, 4):
                try:
                    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
                    model_id = "cpierse/wav2vec2-large-xlsr-53-esperanto"
                    print(f"[CONV] Loading wav2vec2 Esperanto model...")
                    self._wav2vec2_processor = Wav2Vec2Processor.from_pretrained(model_id)
                    self._wav2vec2_model     = Wav2Vec2ForCTC.from_pretrained(model_id)
                    self._wav2vec2_model.eval()
                    print("[CONV] wav2vec2 esperanto ready.")
                    break
                except Exception as e:
                    self._wav2vec2_model = None
                    if attempt < 3:
                        print(f"[CONV] wav2vec2 load failed (attempt {attempt}/3): {e} — retrying in 3s...")
                        time.sleep(3)
                    else:
                        print(f"[CONV] wav2vec2 load failed (gave up): {e}")
        return self._wav2vec2_model

    def _transcribe_wav2vec2(self, audio: np.ndarray) -> str:
        import torch
        model     = self._get_wav2vec2()
        processor = self._wav2vec2_processor
        if model is None:
            return ""
        try:
            audio_float = audio.astype(np.float32) / 32768.0
            inputs = processor(audio_float, sampling_rate=16000,
                               return_tensors="pt", padding=True)
            with torch.no_grad():
                logits = model(**inputs).logits
            predicted_ids = torch.argmax(logits, dim=-1)
            text = processor.batch_decode(predicted_ids)[0].strip().lower()
            print(f"[CONV] wav2vec2 STT: {text!r}")
            return text
        except Exception as e:
            print(f"[CONV] wav2vec2 transcribe error: {e}")
            return ""

    def _listen_and_reply(self):
        with self._lock:
            if self._recording:
                return
            self._recording = True
        try:
            sr     = CFG["audio_sample_rate"]
            maxsec = CFG["audio_record_seconds"]
            hub_send("CONV_LISTEN")          # hub shows the MIC icon
            print("CONV_LISTEN")
            audio = _record_audio(maxsec, sr)
            hub_send("CONV_DONE")            # hub returns to the K icon
            ACTIVITY.poke()
            user_text = self._transcribe_wav2vec2(audio)
            if not user_text:
                _speak("Pardonu, mi ne povas aŭdi.", lang="eo")
                return
            print(f"[CONV] User said: {user_text!r}")
            self.history.append({"role": "user", "content": user_text})
            max_turns = CFG["conv_history_turns"] * 2
            if len(self.history) > max_turns:
                self.history = self.history[-max_turns:]
            api_key = CFG.get("groq_api_key", "")
            if not api_key:
                _speak("Mankas la API-ŝlosilo.", lang="eo")
                return
            reply = _groq_chat(history=self.history, system=self.system_prompt,
                               api_key=api_key, model=CFG["groq_model"])
            print(f"[CONV] Robot: {reply!r}")
            self.history.append({"role": "assistant", "content": reply})
            _CULTURE_KEYWORDS = [
                "poezio", "kanto", "muziko", "poemo", "literaturo",
                "kulturo", "zamenhof", "libro", "arte", "kanti", "muzik",
            ]
            if any(kw in reply.lower() for kw in _CULTURE_KEYWORDS):
                self._pending_media_offer = True
                reply_with_offer = reply + (
                    " — Ĉu vi volas aŭdi muzikon aŭ poezion? "
                    "Premu la dekstran butonon por jes."
                )
                _speak(reply_with_offer, lang="eo")
            else:
                self._pending_media_offer = False
                _speak(reply, lang="eo")
        finally:
            with self._lock:
                self._recording = False

    def on_enter(self):
        self.history = []
        self._pending_media_offer = False
        if not CFG.get("groq_api_key"):
            print("[CONV] WARNING: groq_api_key not set.")
        print(f"[CONV] Ready. Difficulty: {self.difficulty}. Press YES to speak.")
        _speak("Saluton! Premu la dekstran butonon por paroli.", lang="eo")
        threading.Thread(target=self._get_wav2vec2, daemon=True).start()

    def on_yes(self):
        ACTIVITY.poke()
        if self._pending_media_offer:
            self._pending_media_offer = False
            target = random.choice([1, 2])
            print(f"MODE:{target}")
            return
        threading.Thread(target=self._listen_and_reply, daemon=True).start()

    def on_no(self):
        ACTIVITY.poke()
        self._pending_media_offer = False
        with self._lock:
            if self._recording:
                return
        self.history = []
        print("[CONV] History cleared.")
        _speak("Konversacio rekomencita.", lang="eo")

    def on_action_hold(self):
        ACTIVITY.poke()
        self._cycle_difficulty()

    def on_sleep(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

    def on_wake(self):
        _speak("Saluton denove!", lang="eo")

    def get_history_summary(self) -> str:
        if not self.history:
            return "(no conversation history)"
        lines = []
        for msg in self.history[-10:]:
            role = "You" if msg["role"] == "user" else "Robot"
            lines.append(f"  {role}: {msg['content']}")
        return "\n".join(lines)


# ============================================================
# ATTRACT MODE
# ============================================================

_ATTRACT_GREETINGS = [
    ("Hej! Czy wiesz, że istnieje język stworzony po to, by łączyć wszystkich ludzi?",              "pl"),
    ("Hey! Did you know there's a language invented specifically to unite all of humanity?",         "en"),
    ("Cześć! Jestem robotem esperanto. Porozmawiajmy o języku, który nie należy do nikogo!",         "pl"),
    ("Hi there! I'm an Esperanto robot. Come discover the world's most democratic language!",       "en"),
    ("One language for the whole world — that was the dream of Ludwig Zamenhof back in 1887!",       "en"),
    ("Saluton! To znaczy 'cześć' w esperanto. Chcesz nauczyć się więcej?",                          "pl"),
    ("Saluton means hello. Dankon means thank you. You already speak two words of Esperanto!",       "en"),
]

_ATTRACT_TEASER_WORDS = [
    ("saluton",   "hello",      "cześć"),
    ("dankon",    "thank you",  "dziękuję"),
    ("ami",       "to love",    "kochać"),
    ("paco",      "peace",      "pokój"),
    ("mondo",     "world",      "świat"),
    ("lingvo",    "language",   "język"),
    ("muziko",    "music",      "muzyka"),
    ("roboto",    "robot",      "robot"),
    ("espero",    "hope",       "nadzieja"),
    ("amiko",     "friend",     "przyjaciel"),
    ("lerni",     "to learn",   "uczyć się"),
    ("paroli",    "to speak",   "mówić"),
]

_ATTRACT_QUIZ_INTROS = [
    ("What does this Esperanto word mean?  ", "en"),
    ("Quick quiz — can you guess what this word means?  ", "en"),
    ("Co znaczy po esperanto słowo:  ", "pl"),
    ("Mam dla ciebie zagadkę! Co znaczy:  ", "pl"),
]

_ATTRACT_MUSIC_INTROS = [
    ("Now listen to a snippet of real Esperanto music!", "en"),
    ("A teraz posłuchaj fragmentu muzyki esperanto!", "pl"),
]

_ATTRACT_POEM_INTROS = [
    ("Now — a snippet of Esperanto poetry!", "en"),
    ("A teraz posłuchaj fragmentu poezji esperanto!", "pl"),
]

_ATTRACT_FACTS = [
    ("Every Esperanto noun ends in -o, every adjective in -a, every verb infinitive in -i!", "en"),
    ("W esperanto wszystkie rzeczowniki kończą się na -o, a przymiotniki na -a. Proste!", "pl"),
    ("The word 'Esperanto' literally means 'one who hopes' — from the root espero, hope!", "en"),
    ("Duolingo has an Esperanto course with millions of learners worldwide!", "en"),
    ("Google Translate obsługuje esperanto! Możesz ćwiczyć w telefonie!", "pl"),
]

_ATTRACT_CTAS = [
    ("Press any button to start exploring! Check the laminated guide next to me.", "en"),
    ("Naciśnij dowolny przycisk żeby zacząć!", "pl"),
]

_ATTRACT_GOODBYES = [
    ("Come back anytime! See you soon!", "en"),
    ("Wróć kiedy chcesz! Do zobaczenia!", "pl"),
    ("Adiaŭ — that means goodbye in Esperanto. Come back soon!", "en"),
]

_ATTRACT_SEQ_TYPES = ["word_quiz", "music_snippet", "poem_snippet", "fun_fact", "full"]


class AttractMode(Mode):
    name = "ATTRACT"

    def __init__(self, music_mode: MediaMode, poems_mode: MediaMode):
        self._music          = music_mode
        self._poems          = poems_mode
        self._active         = False
        self._stop_flag      = False
        self._speaking       = False
        self._last_greet_idx = -1
        self._last_seq_type  = ""

    def _pick_greeting(self) -> tuple:
        n = len(_ATTRACT_GREETINGS)
        idx = random.randint(0, n - 1)
        if idx == self._last_greet_idx and n > 1:
            idx = (idx + 1) % n
        self._last_greet_idx = idx
        return _ATTRACT_GREETINGS[idx]

    def _pick_seq_type(self) -> str:
        choices = [t for t in _ATTRACT_SEQ_TYPES if t != self._last_seq_type]
        t = random.choice(choices)
        self._last_seq_type = t
        return t

    def _sleep_check(self, seconds: float) -> bool:
        steps = int(seconds / 0.1)
        for _ in range(steps):
            if self._stop_flag:
                return True
            time.sleep(0.1)
        return False

    def _play_snippet(self, entries: list, directory, duration_s: int = 10) -> dict | None:
        if not entries:
            return None
        entry = random.choice(entries)
        path  = directory / entry["filename"]
        if not path.exists():
            return None
        _ensure_mixer()
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.play()
        if self._sleep_check(duration_s):
            pygame.mixer.music.stop()
            return None
        pygame.mixer.music.stop()
        return entry

    def _seq_word_quiz(self):
        text, lang = self._pick_greeting()
        _speak(text, lang=lang)
        if self._stop_flag: return
        intro_text, intro_lang = random.choice(_ATTRACT_QUIZ_INTROS)
        word, en_meaning, pl_meaning = random.choice(_ATTRACT_TEASER_WORDS)
        _speak(intro_text, lang=intro_lang)
        _speak(word, lang="eo")
        if self._sleep_check(2.5): return
        if UI_LANG == "pl":
            _speak(f"To znaczy: {pl_meaning}!", lang="pl")
        else:
            _speak(f"It means: {en_meaning}!", lang="en")
        if self._stop_flag: return
        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _seq_music_snippet(self):
        text, lang = self._pick_greeting()
        _speak(text, lang=lang)
        if self._stop_flag: return
        intro_text, intro_lang = random.choice(_ATTRACT_MUSIC_INTROS)
        _speak(intro_text, lang=intro_lang)
        if self._stop_flag: return
        entry = self._play_snippet(self._music.entries, self._music.directory, duration_s=12)
        if entry:
            title  = entry.get("title") or entry["filename"]
            artist = entry.get("artist") or entry.get("author", "")
            ans = f"That was: {title}" + (f" — {artist}." if artist else ".")
            _speak(ans, lang="pl")
        if self._stop_flag: return
        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _seq_poem_snippet(self):
        text, lang = self._pick_greeting()
        _speak(text, lang=lang)
        if self._stop_flag: return
        intro_text, intro_lang = random.choice(_ATTRACT_POEM_INTROS)
        _speak(intro_text, lang=intro_lang)
        if self._stop_flag: return
        entry = self._play_snippet(self._poems.entries, self._poems.directory, duration_s=12)
        if entry:
            title  = entry.get("title") or entry["filename"]
            author = entry.get("author") or entry.get("artist", "")
            ans = f"That was: {title}" + (f" — {author}." if author else ".")
            _speak(ans, lang="pl")
        if self._stop_flag: return
        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _seq_fun_fact(self):
        text, lang = self._pick_greeting()
        _speak(text, lang=lang)
        if self._stop_flag: return
        fact_text, fact_lang = random.choice(_ATTRACT_FACTS)
        _speak(fact_text, lang=fact_lang)
        if self._stop_flag: return
        word, en_meaning, pl_meaning = random.choice(_ATTRACT_TEASER_WORDS)
        _speak("Oto dodatkowe słówko:", lang="pl")
        _speak(word, lang="eo")
        _speak(f"To znaczy: {pl_meaning}!", lang="pl")  # lub pl_meaning
        if self._stop_flag: return
        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _seq_full(self):
        text, lang = self._pick_greeting()
        _speak(text, lang=lang)
        if self._stop_flag: return
        intro_text, intro_lang = random.choice(_ATTRACT_QUIZ_INTROS)
        word, en_meaning, pl_meaning = random.choice(_ATTRACT_TEASER_WORDS)
        _speak(intro_text, lang=intro_lang)
        _speak(word, lang="eo")
        if self._sleep_check(2.5): return
        _speak(f"To znaczy: {en_meaning}!", lang="pl")
        if self._stop_flag: return
        if random.random() < 0.5:
            intro_text, intro_lang = random.choice(_ATTRACT_MUSIC_INTROS)
            _speak(intro_text, lang=intro_lang)
            if self._stop_flag: return
            self._play_snippet(self._music.entries, self._music.directory, duration_s=10)
        else:
            intro_text, intro_lang = random.choice(_ATTRACT_POEM_INTROS)
            _speak(intro_text, lang=intro_lang)
            if self._stop_flag: return
            self._play_snippet(self._poems.entries, self._poems.directory, duration_s=10)
        if self._stop_flag: return
        fact_text, fact_lang = random.choice(_ATTRACT_FACTS)
        _speak(fact_text, lang=fact_lang)
        if self._stop_flag: return
        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _run_sequence(self):
        self._speaking = True
        hub_send("ATTRACT_SPEAK_START")   # hub pauses its attract-lost timer
        print("ATTRACT_SPEAKING")
        try:
            seq_type = self._pick_seq_type()
            print(f"[ATTRACT] Sequence: {seq_type}")
            if   seq_type == "word_quiz":      self._seq_word_quiz()
            elif seq_type == "music_snippet":  self._seq_music_snippet()
            elif seq_type == "poem_snippet":   self._seq_poem_snippet()
            elif seq_type == "fun_fact":       self._seq_fun_fact()
            elif seq_type == "full":           self._seq_full()
        except Exception as e:
            print(f"[ATTRACT] Sequence error: {e}")
        finally:
            self._speaking = False
            hub_send("ATTRACT_SPEAK_DONE")
            print("ATTRACT_IDLE")

    def _loop(self):
        while self._active and not self._stop_flag:
            self._run_sequence()
            for _ in range(250):
                if not self._active or self._stop_flag:
                    return
                time.sleep(0.1)

    def on_enter(self):
        self._stop_flag = False
        self._active    = True
        _tts_stop_event.clear()
        print("[ATTRACT] Active.")
        threading.Thread(target=self._loop, daemon=True).start()

    def _stop_sequence(self):
        self._active    = False
        self._stop_flag = True
        _request_tts_stop()
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

    def _speak_instructions(self):
            if UI_LANG == "pl":
                _speak(
                    "Witaj! Jestem robotem esperanto. Mam cztery tryby: Fiszki, Poezja, Muzyka i Konwersacja z AI. "
                    "Przytrzymaj lewy przycisk, żeby otworzyć menu. Miłej zabawy!",
                    lang="pl"
                )
            else:
                _speak(
                    "Welcome! I'm an Esperanto robot. I have four modes: Flashcards, Poems, Music, and AI Conversation. "
                    "Press and hold the left button to open the menu.",
                    lang="en"
                )

    def on_yes(self):
        self._stop_sequence()
        ACTIVITY.poke()
        for _ in range(40):
            if not self._speaking:
                break
            time.sleep(0.1)
        _tts_stop_event.clear()
        self._speak_instructions()

    def on_no(self):
        self.on_yes()

    def on_action_hold(self): pass

    def on_sleep(self):
        self._stop_sequence()

    def on_wake(self):
        if not self._active:
            self.on_enter()

    def on_attract_lost(self):
        self._active = False
        threading.Thread(target=self._goodbye_then_sleep, daemon=True).start()

    def _goodbye_then_sleep(self):
        for _ in range(600):
            if not self._speaking:
                break
            time.sleep(0.1)
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
        text, lang = random.choice(_ATTRACT_GOODBYES)
        _speak(text, lang=lang)
        print("[ATTRACT] Person left — going to sleep.")
        hub_send("SLEEP")   # put the hub to sleep right after the goodbye

    def on_attract_timeout(self):
        self.on_attract_lost()

    def tick(self): pass


# ============================================================
# MODE MANAGER
# ============================================================

class ModeManager:
    def __init__(self):
        _music_mode   = MediaMode(MUSIC_DIR, "MUSIC", "music.json")
        _poems_mode   = MediaMode(POEMS_DIR, "POEMS", "poems.json")
        _fc_mode      = FlashcardsMode()
        _a0_mode      = A0LessonMode()
        self.modes: list[Mode] = [
            _fc_mode,            # 0 — FLASHCARDS
            _poems_mode,         # 1 — POEMS
            _music_mode,         # 2 — MUSIC
            ConversationMode(),  # 3 — CONVERSATION
            AttractMode(_music_mode, _poems_mode),  # 4 — ATTRACT
            _a0_mode,            # 5 — A0 LESSON
        ]
        self._music_mode = _music_mode
        self._poems_mode = _poems_mode
        self._fc_mode    = _fc_mode
        self._a0_mode    = _a0_mode
        self.tui_mode_changed = threading.Event()
        _music_mode.preload_entries()
        _poems_mode.preload_entries()
        self.current_idx = 0
        self._started    = False
        self._sleeping   = False

    @property
    def current(self) -> Mode:
        return self.modes[self.current_idx]

    def switch_to(self, idx: int):
        idx = idx % len(self.modes)
        if idx == self.current_idx and self._started:
            return
        old = self.current.name
        if self._started:
            if hasattr(self.current, "_stop_sequence"):
                self.current._stop_sequence()
            elif hasattr(self.current, "_stop"):
                self.current._stop()
            if isinstance(self.current, AttractMode):
                for _ in range(30):
                    if not self.current._speaking:
                        break
                    time.sleep(0.1)
        _tts_stop_event.clear()
        self.current_idx = idx
        self._started    = True
        print(f"[MGR] {old} -> {self.current.name}")
        self.current.on_enter()
        if getattr(self, '_ble_send', None):
            self._ble_send(f"MODE:{idx}")
        self.tui_mode_changed.set()

    def handle(self, signal: str):
        if signal.startswith("DEBUG:"):
            # Hub echoes every received command as DEBUG:RX:<cmd> — this is
            # the ACK that the PC -> hub direction works.
            print(f"[hub-ack] {signal}")
            return
        if signal in ("READY",) or signal.startswith("INFO:") or signal.startswith("WARN:"):
            print(f"[hub-init] {signal}")
            if signal == "READY" and getattr(self, '_ble_send', None):
                self._ble_send(f"MODE:{self.current_idx}")
            return
        ACTIVITY.poke()
        m = self.current
        if   signal == "YES":         m.on_yes()
        elif signal == "NO":          m.on_no()
        elif signal == "ACTION_HOLD": m.on_action_hold()
        elif signal == "SLEEP":
            self._sleeping = True
            ACTIVITY.set_sleeping(True)
            m.on_sleep()
            print("[MGR] Robot sleeping.")
        elif signal == "WAKE":
            self._sleeping = False
            ACTIVITY.set_sleeping(False)
            m.on_wake()
            print("[MGR] Robot awake.")
        elif signal == "ATTRACT_ENTER":
            self.switch_to(4)
        elif signal == "ATTRACT_LOST":
            if isinstance(self.current, AttractMode):
                self.current.on_attract_lost()
        elif signal == "ATTRACT_TIMEOUT":
            if isinstance(self.current, AttractMode):
                self.current.on_attract_timeout()
        elif signal == "ATTRACT_EXIT":
            if isinstance(self.current, AttractMode):
                self.current._stop_sequence()
        elif signal in ("ATTRACT_SPEAKING", "ATTRACT_IDLE"):
            pass
        elif signal.startswith("MODE:"):
            try:
                self.switch_to(int(signal.split(":")[1].strip()))
            except (ValueError, IndexError):
                print(f"[MGR] Bad MODE signal: {signal!r}")
        elif signal == "MEDIA_PAUSE":
            if hasattr(self.current, "pause"):
                self.current.pause()
        elif signal == "MEDIA_RESUME":
            if hasattr(self.current, "unpause"):
                self.current.unpause()
        elif signal.startswith("FILTER:"):
            unit = signal.split(":", 1)[1].strip()
            self._fc_mode.set_filter(unit if unit.lower() != "none" else None)
            self.switch_to(0)
        elif signal.startswith("LESSON_FILTER:"):
            unit = signal.split(":", 1)[1].strip()
            self._fc_mode.set_filter(unit)
            self.switch_to(0)
        elif signal == "LESSON_EXIT":
            self.switch_to(0)
        elif signal.startswith("CONV_") or signal.startswith("["):
            pass
        else:
            print(f"[MGR] Unknown signal: {signal!r}")

    def tick(self):
        if not self._sleeping:
            self.current.tick()


# ============================================================
# ┌──────────────────────────────────────────────────────────┐
# │                  TERMINAL TUI SYSTEM                     │
# │                                                          │
# │  PASSIVE & REACTIVE — locks to current hub mode.         │
# │  No manual exit from a sub-TUI. Only a new MODE: signal  │
# │  (from hub) will switch the active sub-TUI.              │
# └──────────────────────────────────────────────────────────┘

# Shared event: whenever the hub changes mode, this is set.
# Each sub-TUI checks it in its loop and exits when triggered.
_tui_mode_switch = threading.Event()


def _sep(char: str = "─", width: int = 62) -> str:
    return char * width


def _header(title: str, mode_idx: int) -> str:
    MODE_ICONS = {
        0: "🃏", 1: "📜", 2: "🎵", 3: "💬", 4: "✨", 5: "📖"
    }
    icon = MODE_ICONS.get(mode_idx, "•")
    bar  = _sep()
    return f"\n{bar}\n  {icon}  {title}  (MODE {mode_idx} — locked until hub changes)\n{bar}"


def _mode_switched() -> bool:
    """Returns True if a mode change arrived — each sub-TUI calls this to know when to exit."""
    return _tui_mode_switch.is_set()


def _wait_for_input_or_switch(prompt: str) -> str | None:
    """
    Non-blocking input: returns user input string, or None if a mode switch
    arrived while waiting (sub-TUI should exit).

    When a mode switch arrives mid-input the function returns None immediately.
    The dangling input() thread is daemon so it dies with the process; if the
    user presses Enter after the switch the output is simply discarded.
    """
    while True:
        result: list[str | None] = [None]
        ready  = threading.Event()

        def _read():
            try:
                result[0] = input(prompt)
            except (EOFError, KeyboardInterrupt):
                result[0] = ""
            ready.set()

        t = threading.Thread(target=_read, daemon=True)
        t.start()

        while not ready.is_set():
            if _tui_mode_switch.is_set():
                # Print a blank line so the dangling cursor doesn't merge with next header
                print()
                return None
            time.sleep(0.05)

        # Input finished — but check if a switch also happened (race)
        if _tui_mode_switch.is_set():
            return None

        raw = result[0] or ""

        # Global command, available in every sub-TUI:
        #   hub <CMD>  — send a raw line to the hub (e.g. "hub MODE:2",
        #   "hub SLEEP", "hub CONV_LISTEN"). The hub answers DEBUG:RX:<CMD>,
        #   which is the live proof that two-way BLE works.
        if raw.strip().lower().startswith("hub "):
            payload = raw.strip()[4:].strip()
            if payload:
                hub_send(payload)
                print(f"  [HUB] sent: {payload!r} — expect [hub-ack] DEBUG:RX:{payload}")
            continue

        return raw


# ─── FLASHCARDS TUI ───────────────────────────────────────

def _fmt_word(w: dict, idx: int) -> str:
    word  = w.get("word", "?")
    unit  = w.get("unit", "")
    corr  = w.get("correct_count", 0)
    wrong = w.get("wrong_count", 0)
    ease  = w.get("sr_ease", 2.5)
    due   = w.get("next_review", "")[:16]
    return (f"  {idx+1:>4}. {word:<22} [{unit:<12}]  "
            f"✓{corr:>3}  ✗{wrong:>3}  ease={ease:.1f}  due={due}")


def _tui_flashcards(manager: ModeManager):
    fc = manager._fc_mode
    print(_header("FLASHCARDS", 0))
    print("  Commands:")
    print("    yes / y          — mark current word CORRECT")
    print("    no  / n          — mark current word WRONG + hear definition")
    print("    hint / h         — hear definition without marking")
    print("    next             — skip to next word (no score change)")
    print("    repeat / r       — repeat current word TTS")
    print("    stats            — session & overall stats")
    print("    list [N]         — list all words (optional: top N by wrong count)")
    print("    due              — list only words due for review now")
    print("    filter <unit>    — filter by unit name (or 'none' to clear)")
    print("    weakest          — show 10 most-wrong words")
    print("    best             — show 10 most-correct words")
    print("    word <text>      — jump to a specific word by text")
    print(_sep())

    while not _mode_switched():
        raw = _wait_for_input_or_switch("[FC]> ")
        if raw is None:
            break  # mode switched
        cmd = raw.strip().lower()

        if cmd in ("yes", "y"):
            fc.on_yes()

        elif cmd in ("no", "n"):
            fc.on_no()

        elif cmd in ("hint", "h"):
            fc.on_action_hold()

        elif cmd == "next":
            fc._next()
            print(f"  → {fc.current.get('word', '?')}")

        elif cmd in ("repeat", "r"):
            word = fc.current.get("word", "")
            pron = fc.current.get("pronunciation", "")
            print(f"  Repeating: {word}  [{pron}]")
            threading.Thread(target=_speak_eo_with_hint, args=(word, pron), daemon=True).start()

        elif cmd == "stats":
            s = fc.get_stats()
            print(f"\n  Session: {s['session_correct']} correct, {s['session_wrong']} wrong "
                  f"/ {s['session_total']} total")
            print(f"  Due now: {s['due_now']}  |  Total words: {s['total_words']}")
            print(f"  Active filter: {s['active_filter'] or '(none)'}")
            if s["hardest"]:
                print("  Hardest:")
                for w in s["hardest"]:
                    print(f"    {w['word']:<20} wrong={w.get('wrong_count',0)}")
            print()

        elif cmd.startswith("list"):
            parts = cmd.split()
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            words = fc._all_words
            if limit:
                words = sorted(words, key=lambda w: w.get("wrong_count", 0), reverse=True)[:limit]
            print(f"\n  {'#':>4}  {'Word':<22} {'Unit':<12}  {'✓':>4}  {'✗':>4}  ease   due")
            print("  " + _sep("-", 60))
            for i, w in enumerate(words):
                print(_fmt_word(w, i))
            print(f"  ({len(words)} words)\n")

        elif cmd == "due":
            now   = datetime.now()
            due_w = [w for w in fc.words
                     if datetime.fromisoformat(sr_init(w)["next_review"]) <= now]
            if not due_w:
                print("  No words due for review right now.")
            else:
                print(f"\n  {len(due_w)} word(s) due:")
                for i, w in enumerate(due_w):
                    print(_fmt_word(w, i))
            print()

        elif cmd.startswith("filter"):
            parts = raw.strip().split(None, 1)
            unit = parts[1].strip() if len(parts) > 1 else None
            if unit and unit.lower() == "none":
                unit = None
            fc.set_filter(unit)
            fc._apply_filter()
            fc._announce_filter()
            fc._next()
            print(f"  Filter set to: {unit!r}")

        elif cmd == "weakest":
            top = sorted(fc._all_words,
                         key=lambda w: w.get("wrong_count", 0), reverse=True)[:10]
            print("\n  10 most-wrong words:")
            for i, w in enumerate(top):
                print(_fmt_word(w, i))
            print()

        elif cmd == "best":
            top = sorted(fc._all_words,
                         key=lambda w: w.get("correct_count", 0), reverse=True)[:10]
            print("\n  10 most-correct words:")
            for i, w in enumerate(top):
                print(_fmt_word(w, i))
            print()

        elif cmd.startswith("word "):
            target = cmd[5:].strip()
            match = next((w for w in fc._all_words
                          if w.get("word", "").lower() == target.lower()), None)
            if match:
                fc.current = match
                fc.shown_definition = False
                print(f"  Jumped to: {match['word']}")
                threading.Thread(
                    target=_speak_eo_with_hint,
                    args=(match["word"], match.get("pronunciation", "")),
                    daemon=True
                ).start()
            else:
                print(f"  Word not found: {target!r}")

        elif cmd in ("", "help", "?"):
            print("  Commands: yes | no | hint | next | repeat | stats | list [N]")
            print("            due | filter <unit> | weakest | best | word <text>")

        else:
            print(f"  Unknown command: {raw!r}  (type 'help' for list)")

    print("[FC] Mode switch received — exiting Flashcards TUI.")


# ─── MEDIA TUI (shared for MUSIC and POEMS) ───────────────

def _fmt_entry(i: int, entry: dict, current_idx: int) -> str:
    marker = "▶" if i == current_idx else " "
    title  = entry.get("title") or entry.get("filename", "?")
    artist = entry.get("artist") or entry.get("author", "")
    plays  = entry.get("play_count", 0)
    rating = ("★" * entry["rating"]) if entry.get("rating") else ""
    detail = f"  — {artist}" if artist else ""
    return (f"  {marker} {i+1:>4}. {title}{detail}"
            f"  [{plays}x]{('  ' + rating) if rating else ''}")


def _tui_media(manager: ModeManager, mode: MediaMode, mode_idx: int):
    name = mode.name
    print(_header(name, mode_idx))
    print("  Commands:")
    print("    list / l         — show all tracks")
    print("    <number>         — jump to track N")
    print("    next / >         — next track (adaptive)")
    print("    prev / <         — previous track")
    print("    pause / p        — pause playback")
    print("    resume / u       — resume playback")
    print("    toggle / t       — toggle pause/resume")
    print("    stop / s         — stop playback")
    print("    play             — play current track from start")
    print("    random / r       — random track")
    print("    info / i         — read metadata (TTS)")
    print("    now              — show now-playing")
    print("    vol <0-100>      — set volume")
    print("    rate <1-5>       — rate current track")
    print("    search <text>    — search tracks by title/artist")
    print(_sep())

    while not _mode_switched():
        raw = _wait_for_input_or_switch(f"[{name.lower()}]> ")
        if raw is None:
            break
        cmd = raw.strip().lower()

        if cmd in ("list", "l"):
            if not mode.entries:
                print(f"  No tracks loaded.")
            else:
                print(f"\n  {name} — {len(mode.entries)} track(s):")
                for i, e in enumerate(mode.entries):
                    print(_fmt_entry(i, e, mode.index))
                print()

        elif cmd in ("next", ">"):
            mode.on_yes()
            e = mode.entries[mode.index] if mode.entries else {}
            print(f"  ▶ {e.get('title') or e.get('filename', '?')}")

        elif cmd in ("prev", "<"):
            mode.on_no()
            e = mode.entries[mode.index] if mode.entries else {}
            print(f"  ▶ {e.get('title') or e.get('filename', '?')}")

        elif cmd in ("pause", "p"):
            mode.pause()

        elif cmd in ("resume", "u"):
            mode.unpause()

        elif cmd in ("toggle", "t"):
            mode.toggle_pause()
            print(f"  {'Paused' if mode.paused else 'Playing'}")

        elif cmd in ("stop", "s"):
            mode._stop()
            print("  Stopped.")

        elif cmd == "play":
            mode._play_current()
            e = mode.entries[mode.index] if mode.entries else {}
            print(f"  ▶ {e.get('title') or e.get('filename', '?')}")

        elif cmd in ("random", "r"):
            if mode.entries:
                idx = random.randint(0, len(mode.entries) - 1)
                mode.jump_to(idx)
                e = mode.entries[idx]
                print(f"  ▶ {e.get('title') or e.get('filename', '?')}")
            else:
                print("  No tracks loaded.")

        elif cmd in ("info", "i"):
            threading.Thread(target=mode.on_action_hold, daemon=True).start()

        elif cmd == "now":
            print(f"  {mode.now_playing()}")

        elif cmd.startswith("vol "):
            try:
                vol = int(cmd[4:].strip())
                mode.set_volume(vol / 100.0)
            except ValueError:
                print("  Usage: vol <0-100>")

        elif cmd.startswith("rate "):
            try:
                stars = int(cmd[5:].strip())
                mode.rate_current(stars)
            except ValueError:
                print("  Usage: rate <1-5>")

        elif cmd.startswith("search "):
            query = raw.strip()[7:].lower()
            results = [
                e for e in mode.entries
                if query in (e.get("title") or "").lower()
                or query in (e.get("artist") or e.get("author") or "").lower()
            ]
            if results:
                print(f"\n  Found {len(results)} match(es):")
                for e in results:
                    i = mode.entries.index(e)
                    print(_fmt_entry(i, e, mode.index))
                print()
            else:
                print(f"  No matches for: {query!r}")

        elif cmd.isdigit():
            n = int(cmd)
            if 1 <= n <= len(mode.entries):
                mode.jump_to(n - 1)
                e = mode.entries[n - 1]
                print(f"  ▶ {e.get('title') or e.get('filename', '?')}")
            else:
                print(f"  Out of range (1–{len(mode.entries)}).")

        elif cmd in ("", "help", "?"):
            print("  Commands: list | <n> | next | prev | pause | resume | toggle | stop")
            print("            play | random | info | now | vol <n> | rate <1-5> | search <text>")

        else:
            print(f"  Unknown command: {raw!r}  (type 'help' for list)")

    print(f"[{name}] Mode switch received — exiting {name} TUI.")


# ─── CONVERSATION TUI ─────────────────────────────────────

def _tui_conversation(manager: ModeManager):
    conv: ConversationMode = manager.modes[3]
    print(_header("CONVERSATION", 3))
    print("  Commands:")
    print("    speak / s        — trigger push-to-talk (same as hub YES button)")
    print("    cancel / c       — cancel current turn + clear history")
    print("    difficulty / d   — cycle difficulty A1 → B1 → C1")
    print("    history          — show last 10 conversation turns")
    print("    clear            — clear conversation history")
    print("    status           — show current difficulty and recording state")
    print("    inject <text>    — inject a user message directly (skip STT)")
    print(_sep())

    while not _mode_switched():
        raw = _wait_for_input_or_switch("[CONV]> ")
        if raw is None:
            break
        cmd = raw.strip().lower()

        if cmd in ("speak", "s"):
            conv.on_yes()

        elif cmd in ("cancel", "c"):
            conv.on_no()

        elif cmd in ("difficulty", "d"):
            conv.on_action_hold()

        elif cmd == "history":
            print(conv.get_history_summary())

        elif cmd == "clear":
            conv.history = []
            print("  History cleared.")
            _speak("Konversacio rekomencita.", lang="eo")

        elif cmd == "status":
            rec = "RECORDING" if conv._recording else "idle"
            print(f"  Difficulty: {conv.difficulty}  |  State: {rec}")
            print(f"  History turns: {len(conv.history)}")

        elif cmd.startswith("inject "):
            text = raw.strip()[7:].strip()
            if text:
                conv.history.append({"role": "user", "content": text})
                api_key = CFG.get("groq_api_key", "")
                if api_key:
                    def _reply():
                        reply = _groq_chat(
                            history=conv.history,
                            system=conv.system_prompt,
                            api_key=api_key,
                            model=CFG["groq_model"],
                        )
                        print(f"  Robot: {reply!r}")
                        conv.history.append({"role": "assistant", "content": reply})
                        _speak(reply, lang="eo")
                    threading.Thread(target=_reply, daemon=True).start()
                else:
                    print("  No API key set.")
            else:
                print("  Usage: inject <your esperanto text>")

        elif cmd in ("", "help", "?"):
            print("  Commands: speak | cancel | difficulty | history | clear | status | inject <text>")

        else:
            print(f"  Unknown command: {raw!r}  (type 'help' for list)")

    print("[CONV] Mode switch received — exiting Conversation TUI.")


# ─── ATTRACT TUI ──────────────────────────────────────────

def _tui_attract(manager: ModeManager):
    attract: AttractMode = manager.modes[4]
    print(_header("ATTRACT MODE", 4))
    print("  Commands:")
    print("    status           — show attract state (active/speaking/idle)")
    print("    stop             — stop current sequence")
    print("    restart          — restart attract loop")
    print("    instruct         — play instructions TTS")
    print("    music            — play a music snippet now")
    print("    poem             — play a poem snippet now")
    print("    word             — speak a random teaser word")
    print(_sep())

    while not _mode_switched():
        raw = _wait_for_input_or_switch("[ATTRACT]> ")
        if raw is None:
            break
        cmd = raw.strip().lower()

        if cmd == "status":
            print(f"  Active: {attract._active}  "
                  f"Speaking: {attract._speaking}  "
                  f"StopFlag: {attract._stop_flag}")

        elif cmd == "stop":
            attract._stop_sequence()
            print("  Sequence stopped.")

        elif cmd == "restart":
            attract._stop_sequence()
            time.sleep(0.5)
            attract.on_enter()
            print("  Attract loop restarted.")

        elif cmd == "instruct":
            threading.Thread(target=attract._speak_instructions, daemon=True).start()

        elif cmd == "music":
            def _snip():
                attract._play_snippet(
                    attract._music.entries, attract._music.directory, duration_s=12
                )
            threading.Thread(target=_snip, daemon=True).start()

        elif cmd == "poem":
            def _snip():
                attract._play_snippet(
                    attract._poems.entries, attract._poems.directory, duration_s=12
                )
            threading.Thread(target=_snip, daemon=True).start()

        elif cmd == "word":
            word, en_m, pl_m = random.choice(_ATTRACT_TEASER_WORDS)
            def _say():
                _speak(word, lang="eo")
                _speak(f"To znaczy: {pl_m}!", lang="pl")   # zamiast en
            threading.Thread(target=_say, daemon=True).start()
            print(f"  → {word} = {en_m}")

        elif cmd in ("", "help", "?"):
            print("  Commands: status | stop | restart | instruct | music | poem | word")

        else:
            print(f"  Unknown command: {raw!r}  (type 'help' for list)")

    print("[ATTRACT] Mode switch received — exiting Attract TUI.")


# ─── A0 LESSON TUI ────────────────────────────────────────

def _tui_lesson(manager: ModeManager):
    a0: A0LessonMode = manager._a0_mode
    print(_header("A0 LESSON", 5))
    print("  Commands:")
    print("    next / y         — next step (hub YES)")
    print("    repeat / n       — repeat current step (hub NO)")
    print("    progress         — show current lesson and step")
    print("    restart          — restart current lesson from step 1")
    print("    lesson <1-4>     — jump to a specific lesson")
    print("    intro            — re-read lesson intro")
    print(_sep())

    while not _mode_switched():
        raw = _wait_for_input_or_switch("[A0]> ")
        if raw is None:
            break
        cmd = raw.strip().lower()

        if cmd in ("next", "y", "yes"):
            a0.on_yes()

        elif cmd in ("repeat", "n", "no"):
            a0.on_no()

        elif cmd == "progress":
            print(f"  {a0.get_progress()}")

        elif cmd == "restart":
            a0.step_idx  = 0
            a0._done     = False
            a0._in_lesson = True
            threading.Thread(target=a0._speak_step, daemon=True).start()
            print(f"  Restarted lesson {a0.lesson_idx+1} from step 1.")

        elif cmd.startswith("lesson "):
            try:
                n = int(cmd.split()[1]) - 1
                if 0 <= n < len(_A0_LESSONS):
                    a0.lesson_idx = n
                    a0.step_idx   = 0
                    a0._done      = False
                    threading.Thread(target=a0._start_lesson, daemon=True).start()
                else:
                    print(f"  Lesson out of range (1–{len(_A0_LESSONS)}).")
            except (ValueError, IndexError):
                print("  Usage: lesson <1-4>")

        elif cmd == "intro":
            a0.on_action_hold()

        elif cmd in ("", "help", "?"):
            print("  Commands: next | repeat | progress | restart | lesson <n> | intro")

        else:
            print(f"  Unknown command: {raw!r}  (type 'help' for list)")

    print("[A0] Mode switch received — exiting Lesson TUI.")


# ─── MASTER TUI DISPATCHER ────────────────────────────────

_MODE_NAMES = {
    0: "FLASHCARDS",
    1: "POEMS",
    2: "MUSIC",
    3: "CONVERSATION",
    4: "ATTRACT",
    5: "A0 LESSON",
}


def _terminal_tui(manager: ModeManager):
    """
    Master TUI loop.
    Waits for a mode change signal, then locks into the
    appropriate sub-TUI.  There is NO manual exit from a
    sub-TUI — only a new MODE: signal from the hub switches it.
    """
    print("\n" + _sep("═"))
    print("  ESPERO-BOT TERMINAL  —  locked-mode TUI")
    print("  Waiting for hub to set mode…")
    print("  Global command: hub <CMD>  — send a raw line to the hub")
    print("  (e.g. 'hub MODE:2', 'hub SLEEP' — hub replies DEBUG:RX:<CMD>)")
    print(_sep("═"))

    current_tui_idx = -1

    while True:
        # Wait until the hub changes the mode (or signals at startup)
        while (not _tui_mode_switch.is_set()
               and manager.current_idx == current_tui_idx):
            time.sleep(0.1)
        _tui_mode_switch.clear()

        idx = manager.current_idx
        if idx == current_tui_idx:
            continue  # spurious wake

        current_tui_idx = idx
        print(f"\n  *** Hub switched to MODE {idx}: {_MODE_NAMES.get(idx, '?')} ***")

        # Arm the exit trigger for the about-to-start sub-TUI
        _tui_mode_switch.clear()

        if   idx == 0: _tui_flashcards(manager)
        elif idx == 1: _tui_media(manager, manager._poems_mode, 1)
        elif idx == 2: _tui_media(manager, manager._music_mode, 2)
        elif idx == 3: _tui_conversation(manager)
        elif idx == 4: _tui_attract(manager)
        elif idx == 5: _tui_lesson(manager)
        else:
            print(f"  [TUI] Unknown mode index {idx} — waiting for next signal.")


# ============================================================
# BLE / MAIN
# ============================================================

async def _hub_main(manager: ModeManager):
    global _hub_send_fn
    print("[BLE] _hub_main started.")
    attempt = 0

    while True:
        attempt += 1
        print(f"Starting hub connection... (attempt {attempt})")

        device = None
        print(f"[BLE] Scanning 15s for '{HUB_NAME}'...")
        try:
            devices = await BleakScanner.discover(timeout=15.0)
            print(f"[BLE] Scan complete. Found {len(devices)} device(s):")
            for d in devices:
                print(f"[BLE]   {d.name!r} {d.address}")
                if d.name == HUB_NAME:
                    device = d
                    print(f"[BLE] Found: {d.name} {d.address}")
                    break
        except BaseException as e:
            import traceback
            print(f"[BLE] discover() CRASHED: {type(e).__name__}: {e}")
            traceback.print_exc()
        print("[BLE] After discover block.")

        if device is None:
            print(f"[ERR] Hub '{HUB_NAME}' not found. Retrying in 5s...")
            await asyncio.sleep(5)
            continue

        attempt = 0
        disconnected_event = asyncio.Event()
        send_queue: asyncio.Queue = asyncio.Queue()
        nus_rx_char = None

        def handle_disconnect(_):
            print("[ERR] Hub disconnected — reconnecting in 3s...")
            disconnected_event.set()

        rx_buf = [""]

        def handle_rx(_, data: bytearray):
            text = data.decode("utf-8", "ignore")
            for ch in text:
                if ch == "\n":
                    line = rx_buf[0].strip()
                    rx_buf[0] = ""
                    if line:
                        _signal_queue.put(line)
                else:
                    rx_buf[0] += ch

        def handle_pybricks_event(_, data: bytearray):
            if data and data[0] == EVT_WRITE_STDOUT:
                handle_rx(_, data[1:])

        try:
            async with BleakClient(device, disconnected_callback=handle_disconnect) as client:
                await client.start_notify(PYBRICKS_CMD_UUID, handle_pybricks_event)
                try:
                    await client.start_notify(NUS_TX_UUID, handle_rx)
                except Exception:
                    pass

                for svc in client.services:
                    for char in svc.characteristics:
                        print(f"[BLE] char: {char.uuid}  props: {char.properties}")
                        if char.uuid.lower() == NUS_RX_UUID.lower():
                            nus_rx_char = char

                # Hub capabilities: first uint16 LE = max characteristic write
                # size. Stdin payload per write = that minus 1 command byte.
                max_stdin_chunk = 19
                try:
                    caps = await client.read_gatt_char(PYBRICKS_CAP_UUID)
                    max_stdin_chunk = max(int.from_bytes(caps[0:2], "little") - 1, 1)
                    print(f"[BLE] Hub capabilities: max stdin chunk = {max_stdin_chunk} B")
                except Exception as e:
                    print(f"[BLE] Capabilities read failed ({e}) — using {max_stdin_chunk} B chunks")

                print("[OK] Hub connected. Waiting for signals...")

                try:
                    await client.write_gatt_char(
                        PYBRICKS_CMD_UUID, bytes([CMD_START_PROGRAM]), response=True
                    )
                    print("[BLE] Hub program started.")
                except Exception as e:
                    print(f"[BLE] Could not auto-start hub program (already running?): {e}")

                async def _sender():
                    while not disconnected_event.is_set():
                        try:
                            msg = await asyncio.wait_for(send_queue.get(), timeout=0.1)
                            data = (msg + "\n").encode("utf-8")
                            if nus_rx_char:
                                # Legacy firmware (< 3.3): raw write to NUS RX
                                await client.write_gatt_char(nus_rx_char, data, response=False)
                            else:
                                # Pybricks Profile v1.3+: WRITE_STDIN command,
                                # chunked to the hub's max write size
                                for i in range(0, len(data), max_stdin_chunk):
                                    chunk = data[i:i + max_stdin_chunk]
                                    await client.write_gatt_char(
                                        PYBRICKS_CMD_UUID,
                                        bytes([CMD_WRITE_STDIN]) + chunk,
                                        response=True,
                                    )
                            print(f"[BLE→hub] {msg!r}")
                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            print(f"[BLE] Send error: {e}")

                sender_task = asyncio.create_task(_sender())
                manager._ble_send = send_queue.put_nowait
                _hub_send_fn = send_queue.put_nowait

                while not disconnected_event.is_set():
                    try:
                        line = _signal_queue.get_nowait()
                    except queue.Empty:
                        manager.tick()
                        await asyncio.sleep(0.05)
                        continue

                    if line is None:
                        break

                    if any(s in line for s in ("SystemExit", "program was")):
                        print(f"[hub-sys] {line}")
                        break

                    if "Traceback" in line or line.startswith("  File"):
                        print(f"[hub-sys] {line}")
                        continue

                    print(f"[hub] {line}")

                    # Intercept MODE: signals to trigger TUI switch
                    if line.startswith("MODE:"):
                        try:
                            new_idx = int(line.split(":")[1].strip())
                            manager.handle(line)
                            manager.tick()
                            _tui_mode_switch.set()   # ← wake up the TUI dispatcher
                            continue
                        except (ValueError, IndexError):
                            pass

                    manager.handle(line)
                    manager.tick()

                    # Also wake TUI on ATTRACT_ENTER (which internally calls switch_to(4))
                    if line in ("ATTRACT_ENTER",):
                        _tui_mode_switch.set()

                sender_task.cancel()

        except Exception as e:
            print(f"[ERR] BLE error: {e}")
        finally:
            _hub_send_fn = None
            manager._ble_send = None

        await asyncio.sleep(3)


def _preload_models(manager: ModeManager, done_event: threading.Event = None):
    def _delayed_load():
        for _ in range(120):
            if getattr(manager, '_ble_send', None) is not None:
                break
            time.sleep(0.5)
        time.sleep(2.0)
        conv: ConversationMode = manager.modes[3]
        print("[BOOT] Preloading wav2vec2...")
        conv._get_wav2vec2()
        print("[BOOT] Model preload complete.")
        if done_event:
            done_event.set()

    t = threading.Thread(target=_delayed_load, daemon=False, name="preload-delay")
    t.start()
    return t


def main():
    print(f"\n=== ESPERO-BOT STARTED === (Język: {'POLSKI' if UI_LANG=='pl' else 'ENGLISH'})")
    print(f"   UI_LANG = '{UI_LANG}'  (zmień na górze pliku)\n")
    
    os.chdir(BASE_DIR)
    _flash_hub_py()

    manager_container = [None]
    ble_ready = threading.Event()
    _preload_done = threading.Event()

    def _ble_thread():
        import ctypes
        import traceback
        print("[BLE] Thread started.")
        try:
            ret = ctypes.windll.ole32.CoInitializeEx(None, 0)
            print(f"[BLE] CoInitializeEx returned: {ret}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("[BLE] Creating ModeManager...")
            manager_container[0] = ModeManager()
            manager_container[0]._ble_send = None
            print("[BLE] ModeManager ready.")
            ble_ready.set()
            loop.run_until_complete(_hub_main(manager_container[0]))
        except BaseException as e:
            print(f"[BLE] FATAL: {type(e).__name__}: {e}")
            traceback.print_exc()
            ble_ready.set()
        finally:
            print("[BLE] Thread ending.")
            try:
                loop.close()
            except Exception:
                pass

    ble_t = threading.Thread(target=_ble_thread, name="ble-main")
    ble_t.start()

    ble_ready.wait()
    manager = manager_container[0]

    pygame.init()
    _start_mic_monitor()
    time.sleep(0.5)
    _preload_models(manager, _preload_done)

    # Start TUI — it blocks until mode switch, then auto-locks to that mode
    tui_thread = threading.Thread(
        target=_terminal_tui, args=(manager,), daemon=True, name="terminal-tui"
    )
    tui_thread.start()

    # Trigger initial TUI lock to mode 0 (default)
    _tui_mode_switch.set()

    try:
        ble_t.join()
    except KeyboardInterrupt:
        print("\n[EXIT] Bye.")


if __name__ == "__main__":
    main()