"""
WRO2026 — Esperanto Flashcard Robot
computer.py — main PC logic (English-only source)

Modes:
  0 — FLASHCARDS    (SM-2 spaced repetition + gTTS)
  1 — POEMS         (MP3 playback, metadata from poems/poems.json)
  2 — MUSIC         (MP3 playback, metadata from music/music.json)
  3 — CONVERSATION  (Whisper STT + Groq LLM + gTTS, Esperanto dialogue)
  4 — ATTRACT       (Showcase mode — activates on wake, invites people to interact)

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
"""

import subprocess
import json
import os
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
# "pl" → robot speaks Polish  (+ Esperanto)
# "en" → robot speaks English (+ Esperanto)
# ============================================================

UI_LANG: str = "pl"   # change to "en" for English UI


def _ui(en: str, pl: str) -> str:
    """Return text in the active UI language."""
    return pl if UI_LANG == "pl" else en


def _speak_ui(en: str, pl: str):
    """Speak text in the active UI language."""
    if UI_LANG == "pl":
        _speak(pl, lang="pl")
    else:
        _speak(en, lang="en")


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
_speaking = False
_speaking_lock = threading.Lock()

_tts_stop_event = threading.Event()


def _request_tts_stop():
    """Stop current TTS playback as fast as possible."""
    _tts_stop_event.set()
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass


def eo_to_pl_phonetic(text: str) -> str:
    """Transcribe Esperanto text to phonetic Polish for gTTS.

    Algorithm based on rules from the Parol/vocx project (Martin Rue, MIT Licence):
      https://github.com/martinrue/vocx

    Steps:
      1. Special letters (ĉ ŝ ĝ ĵ ĥ ŭ) are hidden behind Unicode PUA placeholders
         so they don't interfere with the c → ts rule.
      2. Vowel sequences: io → ijo, ia → ija, ie → ije (separate syllable).
      3. c → ts  (Esperanto c = [ts]; Polish TTS doesn't know this).
      4. qu → kw (absorbed Latinisms).
      5. Restore placeholders → final Polish sequences.
      6. Extra fixes for PL TTS:
           - final -on / -an / -en → -onn / -ann / -enn
             (prevents nasal vowel rendering as in French)
           - -aŭ / -eŭ (diphthongs) → -ał / -eł  (already handled via ŭ → ł)
    """
    # Unicode Private Use Area placeholders
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

    # Vowel sequences
    for src, dst in [("io", "ijo"), ("Io", "Ijo"), ("IO", "IJO"),
                     ("ia", "ija"), ("Ia", "Ija"),
                     ("ie", "ije"), ("Ie", "Ije")]:
        result = result.replace(src, dst)

    # qu → kw (before c → ts substitution)
    result = result.replace("qu", "kw").replace("Qu", "Kw").replace("QU", "KW")

    # c → ts (safe — ĉ is hidden behind placeholder)
    result = result.replace("c", "ts").replace("C", "Ts")

    # Restore placeholders → Polish sequences
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

    # Prevent nasal vowel rendering of final -on/-an/-en by Polish TTS
    result = re.sub(r'on\b', 'onn', result)
    result = re.sub(r'an\b', 'ann', result)
    result = re.sub(r'en\b', 'enn', result)

    return result


def _speak(text: str, lang: str = "en"):
    """Synthesise speech and play via pygame.

    Backend priority:
      1. edge-tts (Microsoft Neural TTS — much more natural voice, free, async)
         Install: pip install edge-tts
         Falls back silently to gTTS if not available.
      2. gTTS (Google TTS — robotic but reliable, requires internet)

    Esperanto (lang='eo'):
      Transcribed to phonetic Polish via eo_to_pl_phonetic() so that the
      Polish TTS engine produces a far better result than any other voice.
    """
    global _speaking
    if _tts_stop_event.is_set():
        return
    if lang == "eo":
        text = eo_to_pl_phonetic(text)
        lang = "pl"

    # Map lang codes to edge-tts voice names
    _EDGE_VOICES = {
        "pl": "pl-PL-MarekNeural",
        "en": "en-GB-RyanNeural",
    }

    tmp = None
    try:
        voice = _EDGE_VOICES.get(lang)
        if voice:
            try:
                import edge_tts, asyncio
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                    tmp = f.name

                async def _edge_synth():
                    communicate = edge_tts.Communicate(text, voice)
                    await communicate.save(tmp)

                asyncio.run(_edge_synth())
            except Exception as e:
                print(f"[TTS] edge-tts failed ({e}), falling back to gTTS")
                tmp = None

        if tmp is None:
            # gTTS fallback
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
    """Speak an Esperanto word via phonetic PL transcription."""
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
    """Build an info string for the current track/poem.

    Returns (text, lang) ready to pass directly to _speak().
    Uses localised fields (title_pl, description_pl, themes_pl) when UI_LANG='pl'
    and they are present in the entry; falls back to English fields otherwise.
    """
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

    _SESSION_CTAS_PL = [
        "Świetna sesja! Teraz posłuchaj muzyki esperanto — otwórz menu i wybierz tryb Muzyka.",
        "Dobra robota! Esperanto ma też prawdziwych poetów. Spróbuj trybu Poezja.",
        "Niezłe! Chcesz użyć tych słów w rozmowie? Otwórz menu i wybierz Rozmowa.",
        "Świetna sesja! Teraz posłuchaj muzyki esperanto — otwórz menu i wybierz tryb Muzyka.",
    ]

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
        # Speak Esperanto word via phonetic PL TTS
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
        # Speak word via phonetic PL TTS
        _speak(word, lang="eo")
        # Definition in UI language
        if UI_LANG == "pl":
            if pl:
                _speak(f"{word} znaczy: {pl}", lang="pl")
            elif en:
                _speak(f"{word} means: {en}", lang="en")
            # Extended definition if it differs from the translation
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

    def _speak_session_summary(self):
        total = self.session_correct + self.session_wrong
        if total == 0:
            return
        weak = max(self._all_words,
                   key=lambda w: w.get("wrong_count", 0), default=None)
        if UI_LANG == "pl":
            summary = (
                f"Podsumowanie sesji: {self.session_correct} dobrze, "
                f"{self.session_wrong} źle z {total} fiszek."
            )
            if weak and weak.get("wrong_count", 0) > 0:
                summary += f" Najtrudniejsze słowo: {weak['word']}."
            cta = random.choice(self._SESSION_CTAS_PL)
            cta_lang = "pl"
        else:
            summary = (
                f"Session summary: {self.session_correct} correct, "
                f"{self.session_wrong} wrong out of {total} cards."
            )
            if weak and weak.get("wrong_count", 0) > 0:
                summary += f" Weakest word: {weak['word']}."
            cta = random.choice(self._SESSION_CTAS_EN)
            cta_lang = "en"
        print(f"[FC] {summary}")
        _speak(summary, lang=UI_LANG)
        _speak(cta, lang=cta_lang)
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
        """Scan disk and JSON, return merged valid entry list (does NOT start playback)."""
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
        """Load entry list without starting playback — call at startup for Attract."""
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

    def jump_to(self, idx: int):
        """Jump to track by index and start playing immediately (called from TUI thread)."""
        if not self.entries:
            print(f"[{self.name}] No entries loaded.")
            return
        self._stop()
        self.index = idx % len(self.entries)
        self._play_current()

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
        # Remember where we were in the music track before TTS stomps the channel
        was_playing = self.playing and not self.paused
        music_pos_ms: float = 0.0
        if was_playing and pygame.mixer.get_init():
            music_pos_ms = pygame.mixer.music.get_pos()  # ms since play() started
            pygame.mixer.music.pause()

        entry = self.entries[self.index] if self.entries else {}
        info_text, info_lang = build_info_speech(entry)
        print(f"[{self.name}] INFO: {info_text}")
        _speak(info_text, lang=info_lang)

        # Reload and resume music from approximately where we left off.
        # pygame.mixer.music.get_pos() counts from the start of play(),
        # not from the file start — and pause/unpause works fine here.
        # However _speak() calls music.load() internally which discards the
        # paused state, so we must reload the file and seek manually.
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
                    print(f"[{self.name}] Could not resume music after info: {e}")

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

_A0_LESSONS_EN = [
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
            ("saluton", "SA-lu-ton",
             "Hello!", "Cześć!"),
            ("saluton", "SA-lu-ton",
             "Saluton means: Hello.", "Saluton znaczy: Cześć."),
            ("dankon",  "DAN-kon",
             "Thank you!", "Dziękuję!"),
            ("dankon",  "DAN-kon",
             "Dankon means: Thank you.", "Dankon znaczy: Dziękuję."),
            ("bonvolu", "bon-VO-lu",
             "Please!", "Proszę!"),
            ("jes",     "yes",
             "Yes!", "Tak!"),
            ("ne",      "ne",
             "No!", "Nie!"),
            ("bonan matenon", "BO-nan ma-TE-non",
             "Good morning!", "Dzień dobry!"),
            ("bonan tagon",   "BO-nan TA-gon",
             "Good day!", "Dobry dzień!"),
            ("ĝis revido",    "djis re-VI-do",
             "Goodbye — see you again!", "Do widzenia — do następnego razu!"),
        ],
        "outro": (
            "You know the basics! "
            "Now go practice in Flashcards mode — press and hold the left button "
            "to open the menu.",
            "Znasz już podstawy! "
            "Ćwicz dalej w trybie Fiszki — przytrzymaj lewy przycisk żeby otworzyć menu.",
        ),
        "filter_cta": None,
    },
    {
        "id": "numbers",
        "title_en": "Numbers",         "title_pl": "Liczby",
        "intro": (
            "In Esperanto, numbers are completely regular. "
            "Learn one through ten and you can count to a million.",
            "W esperanto liczby są całkowicie regularne. "
            "Naucz się od jednego do dziesięciu i możesz liczyć do miliona.",
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
             "Jedenaście. Po prostu dek plus unu — zero wyjątków!"),
        ],
        "outro": (
            "Numbers done! The robot uses SM-2 to track which numbers you find hardest. "
            "Head to Flashcards — Numbers unit — to drill them.",
            "Liczby zaliczone! Robot używa SM-2 żeby śledzić najtrudniejsze słowa. "
            "Przejdź do Fiszek — filtr Liczby — żeby je poćwiczyć.",
        ),
        "filter_cta": "Numbers",
    },
    {
        "id": "culture",
        "title_en": "Esperanto Culture", "title_pl": "Kultura esperanto",
        "intro": (
            "Esperanto isn't just grammar — it has 130 years of poetry, music, and congresses. "
            "Let's learn the words that connect you to that culture.",
            "Esperanto to nie tylko gramatyka — ma 130 lat poezji, muzyki i kongresów. "
            "Nauczymy się słów łączących z tą kulturą.",
        ),
        "steps": [
            ("espero",    "es-PE-ro",
             "Hope. The word Esperanto itself means 'one who hopes'.",
             "Nadzieja. Słowo Esperanto znaczy 'ten, który ma nadzieję'."),
            ("paco",      "PA-tso",
             "Peace.", "Pokój."),
            ("mondo",     "MON-do",
             "World.", "Świat."),
            ("lingvo",    "LING-vo",
             "Language.", "Język."),
            ("kulturo",   "kul-TU-ro",
             "Culture.", "Kultura."),
            ("muziko",    "mu-ZI-ko",
             "Music.", "Muzyka."),
            ("poemo",     "po-E-mo",
             "Poem.", "Wiersz."),
            ("verda stelo","VER-da STE-lo",
             "The green star — symbol of the Esperanto movement.",
             "Zielona gwiazda — symbol ruchu esperanckiego."),
            ("kongreso",  "kon-GRE-so",
             "Congress — Esperanto speakers meet every year at the World Congress.",
             "Kongres — esperantyści spotykają się co roku na Światowym Kongresie."),
            ("zamenhof",  "za-MEN-hof",
             "Zamenhof — Ludwig Lazarus Zamenhof, creator of Esperanto, 1887.",
             "Zamenhof — Ludwig Łazarz Zamenhof, twórca esperanta, 1887."),
        ],
        "outro": (
            "Beautiful! The robot has real Esperanto poetry and music in its archive. "
            "Try Poems mode or Music mode from the menu to hear this culture come alive.",
            "Wspaniale! Robot ma prawdziwą poezję i muzykę esperanto w archiwum. "
            "Wypróbuj tryb Poezja lub Muzyka z menu.",
        ),
        "filter_cta": "Culture",
    },
    {
        "id": "technology",
        "title_en": "Robots and Technology", "title_pl": "Roboty i technologia",
        "intro": (
            "You're talking to a robot right now! "
            "Let's learn the Esperanto words for technology — perfect for this competition.",
            "Właśnie rozmawiasz z robotem! "
            "Nauczymy się esperanckich słów związanych z technologią — idealne na te zawody.",
        ),
        "steps": [
            ("roboto",      "ro-BO-to",
             "Robot!", "Robot!"),
            ("komputilo",   "kom-pu-TI-lo",
             "Computer.", "Komputer."),
            ("sensilo",     "sen-SI-lo",
             "Sensor.", "Czujnik."),
            ("ekrano",      "ek-RA-no",
             "Screen, display.", "Ekran."),
            ("programi",    "pro-GRA-mi",
             "To program — a verb! In Esperanto all verbs end in -i.",
             "Programować — czasownik! W esperanto wszystkie bezokoliczniki kończą się na -i."),
            ("datumoj",     "da-TU-moy",
             "Data.", "Dane."),
            ("aŭtomata",    "aw-to-MA-ta",
             "Automatic, autonomous.", "Automatyczny."),
            ("inteligenta", "in-te-li-GEN-ta",
             "Intelligent.", "Inteligentny."),
            ("artefarita inteligenteco",
             "ar-te-fa-RI-ta in-te-li-gen-TE-tso",
             "Artificial intelligence — three words, completely regular.",
             "Sztuczna inteligencja — trzy słowa, całkowicie regularne."),
            ("inventi",     "in-VEN-ti",
             "To invent. Zamenhof invented Esperanto in 1887.",
             "Wynaleźć. Zamenhof wynalazł esperanto w 1887 roku."),
        ],
        "outro": (
            "Roboto, sensilo, programi — you speak robot Esperanto now! "
            "Drill these in Flashcards with the Technology filter. "
            "Or try the AI Conversation mode to use them in a real sentence.",
            "Roboto, sensilo, programi — mówisz już po esperanto jak robot! "
            "Ćwicz te słowa w Fiszkach z filtrem Technologia. "
            "Albo wypróbuj tryb Rozmowy z AI.",
        ),
        "filter_cta": "Technology",
    },
]

# alias — rest of code uses _A0_LESSONS
_A0_LESSONS = _A0_LESSONS_EN


class A0LessonMode(Mode):
    """Scripted A0 teaching mode — no AI, no tokens.

    Lesson structure:
      intro → steps (word + phonetics + meaning) → outro + CTA

    YES          = next step
    NO           = repeat current step
    ACTION_HOLD  = repeat current lesson title and intro
    """
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
        _speak(intro_pl if UI_LANG == "pl" else intro_en,
               lang=UI_LANG)
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
        # Speak Esperanto word via phonetic PL TTS
        _speak_eo_with_hint(word, pronunciation)
        # Meaning in UI language
        _speak(meaning_pl if UI_LANG == "pl" else meaning_en,
               lang=UI_LANG)

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
                f"Press YES for the next lesson: {next_title}. "
                f"Or press NO for the main menu.",
                f"Naciśnij TAK żeby przejść do lekcji: {next_title}. "
                f"Albo NIE żeby wrócić do menu.",
            )
            self._done = True
        else:
            _speak_ui(
                "You've completed all A0 lessons! "
                "You're ready to explore the full robot. Press NO for the menu.",
                "Ukończyłeś wszystkie lekcje A0! "
                "Możesz teraz eksplorować wszystkie tryby robota. Naciśnij NIE żeby otworzyć menu.",
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
                    "Wszystkie lekcje ukończone! Otwórz menu żeby odkryć inne tryby.",
                )
        elif self._in_lesson:
            self.step_idx += 1
            self._speak_step()

    def on_no(self):
        ACTIVITY.poke()
        if self._done:
            _speak("Opening menu.", lang="en")
            print("LESSON_EXIT")
        elif self._in_lesson:
            self._speak_step()

    def on_action_hold(self):
        ACTIVITY.poke()
        title = self._lesson["title_pl"] if UI_LANG == "pl" else self._lesson["title_en"]
        _speak_ui(f"You're in lesson: {title}.", f"Jesteś w lekcji: {title}.")
        intro_en, intro_pl = self._lesson["intro"]
        _speak(intro_pl if UI_LANG == "pl" else intro_en, lang=UI_LANG)

    def on_sleep(self):
        pass

    def tick(self):
        pass


# ============================================================
# CONVERSATION MODE
# ============================================================

_CONV_SYSTEM_PROMPTS = {
    "A1": (
        "Vi estas afabla esperanto-instruisto por komencantoj (nivelo A1). "
        "Uzu nur bazajn vortojn el la radikaro de Esperanto. "
        "Skribu mallongajn frazojn (maks. 10 vortoj). "
        "Se la studento faras eraron, dolĉe korektu kaj ripetu la ĝustan formon. "
        "Respondu NUR en Esperanto. Temu: ĉiutaga vivo, salutoj, nombroj, koloroj, familio."
    ),
    "B1": (
        "Vi estas amika Esperanto-parolanto je nivelo B1. "
        "Uzu normalan rapidecon kaj variitan vortprovizon. "
        "Respondu nature en Esperanto, korektu erarojn diskrete. "
        "Respondu NUR en Esperanto. Temu: opinioj, vojaĝo, kulturo, historio de Esperanto."
    ),
    "C1": (
        "Vi estas denaska Esperanto-parolanto kun riĉa vortprovizo. "
        "Uzu idiomojn, humuron, kulturajn referencojn, kompleksajn strukturojn. "
        "Ne simpligu vian lingvon. Respondu NUR en Esperanto. "
        "Temu: filozofio, literaturo, esperanta kulturo, nuntempa politiko."
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
            import urllib.request, urllib.error
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "system", "content": system}] + history,
                "max_tokens": 200,
                "temperature": 0.7,
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
        if self._whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                device = CFG["whisper_device"]
                ctype  = "float16" if device == "cuda" else "int8"
                print(f"[CONV] Loading Whisper '{CFG['whisper_model']}' on {device}...")
                self._whisper_model = WhisperModel(
                    CFG["whisper_model"], device=device, compute_type=ctype)
                print("[CONV] Whisper ready.")
            except Exception as e:
                print(f"[CONV] Whisper load failed: {e}")
                self._whisper_model = None
        return self._whisper_model

    def _get_wav2vec2(self):
        if self._wav2vec2_model is None:
            try:
                from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
                model_id = "cpierse/wav2vec2-large-xlsr-53-esperanto"
                print(f"[CONV] Loading wav2vec2 Esperanto model (first run: ~1 GB download)...")
                self._wav2vec2_processor = Wav2Vec2Processor.from_pretrained(model_id)
                self._wav2vec2_model     = Wav2Vec2ForCTC.from_pretrained(model_id)
                self._wav2vec2_model.eval()
                print("[CONV] wav2vec2 esperanto ready.")
            except Exception as e:
                print(f"[CONV] wav2vec2 load failed: {e}")
                self._wav2vec2_model = None
        return self._wav2vec2_model

    def _transcribe_wav2vec2(self, audio: np.ndarray) -> str:
        import torch
        model     = self._get_wav2vec2()
        processor = self._wav2vec2_processor
        if model is None:
            return ""
        try:
            audio_float = audio.astype(np.float32) / 32768.0
            inputs = processor(
                audio_float,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True
            )
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

            print("CONV_LISTEN")
            audio = _record_audio(maxsec, sr)
            ACTIVITY.poke()

            user_text = self._transcribe_wav2vec2(audio)

            if not user_text:
                whisper = self._get_whisper()
                if whisper is None:
                    _speak("Pardonu, mi ne povas aŭdi.", lang="eo")
                    return
                audio_float = audio.astype(np.float32) / 32768.0
                segments, info = whisper.transcribe(audio_float, language=None)
                print(f"[CONV] Whisper fallback STT lang={info.language} conf={info.language_probability:.0%}")
                user_text = " ".join(seg.text.strip() for seg in segments).strip()

            if not user_text:
                print("[CONV] No speech detected.")
                _speak("Mi ne aŭdis vin. Bonvolu paroli denove.", lang="eo")
                return

            print(f"[CONV] User said: {user_text!r}")
            self.history.append({"role": "user", "content": user_text})

            max_turns = CFG["conv_history_turns"] * 2
            if len(self.history) > max_turns:
                self.history = self.history[-max_turns:]

            api_key = CFG.get("groq_api_key", "")
            if not api_key:
                print("[CONV] No GROQ_API_KEY set!")
                _speak("Mankas la API-ŝlosilo. Bonvolu agordi config.json.", lang="eo")
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
                    " — Ĉu vi volas aŭdi muzikon aŭ poezion en Esperanto? "
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
        _speak("Saluton! Mi estas via esperanto-konversaciisto. "
               "Premu la dekstran butonon por paroli.", lang="eo")
        threading.Thread(target=self._get_wav2vec2, daemon=True).start()
        threading.Thread(target=self._get_whisper,  daemon=True).start()

    def on_yes(self):
        ACTIVITY.poke()
        if self._pending_media_offer:
            self._pending_media_offer = False
            target = random.choice([1, 2])
            print(f"[CONV] Media offer accepted → MODE:{target}")
            print(f"MODE:{target}")
            return
        threading.Thread(target=self._listen_and_reply, daemon=True).start()

    def on_no(self):
        ACTIVITY.poke()
        self._pending_media_offer = False
        with self._lock:
            if self._recording:
                print("[CONV] Cancelling current turn.")
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

# ============================================================
# ATTRACT MODE
# ============================================================

_ATTRACT_GREETINGS = [
    ("Hej! Czy wiesz, że istnieje język stworzony po to, by łączyć wszystkich ludzi?",              "pl"),
    ("Hey! Did you know there's a language invented specifically to unite all of humanity?",         "en"),
    ("Cześć! Jestem robotem esperanto. Porozmawiajmy o języku, który nie należy do nikogo!",         "pl"),
    ("Hi there! I'm an Esperanto robot. Come discover the world's most democratic language!",      "en"),
    ("Hola! Bonjour! Hello! Wiesz co łączy te słowa? Każdy naród ma inne — ale jest jedno wspólne!", "pl"),
    ("One language for the whole world — that was the dream of Ludwig Zamenhof back in 1887!",       "en"),
    ("Saluton! To znaczy 'cześć' w esperanto. Chcesz nauczyć się więcej?",                          "pl"),
    ("Saluton means hello. Dankon means thank you. You already speak two words of Esperanto!",       "en"),
    ("Wiedziałeś, że esperanto jest tak proste, że można nauczyć się podstaw w jeden dzień?",        "pl"),
    ("Esperanto has no irregular verbs, no grammatical gender, and a completely logical grammar!",    "en"),
    ("Ponad dwa miliony ludzi na świecie mówi po esperanto. Może Ty też?",                            "pl"),
    ("Esperanto was designed so that anyone — no matter their native tongue — could learn it fast!", "en"),
    ("Czy wiesz, że pierwsze słowniki esperanto miały tylko 900 słów? Teraz jest ich ponad 15 000!", "pl"),
    ("The Esperanto flag is green and white — green for hope, white for peace!",                     "en"),
    ("Zamenhof opublikował esperanto w 1887 roku w Warszawie. Miał wtedy tylko 27 lat!",             "pl"),
]

_ATTRACT_TEASER_WORDS = [
    ("saluton",   "hello",          "cześć"),
    ("dankon",    "thank you",      "dziękuję"),
    ("ami",       "to love",        "kochać"),
    ("paco",      "peace",          "pokój"),
    ("mondo",     "world",          "świat"),
    ("lingvo",    "language",       "język"),
    ("muziko",    "music",          "muzyka"),
    ("poemo",     "poem",           "wiersz"),
    ("roboto",    "robot",          "robot"),
    ("kulturo",   "culture",        "kultura"),
    ("amiko",     "friend",         "przyjaciel"),
    ("espero",    "hope",           "nadzieja"),
    ("lumo",      "light",          "światło"),
    ("kanti",     "to sing",        "śpiewać"),
    ("bela",      "beautiful",      "piękny"),
    ("libro",     "book",           "książka"),
    ("suno",      "sun",            "słońce"),
    ("akvo",      "water",          "woda"),
    ("tero",      "earth",          "ziemia"),
    ("hejmo",     "home",           "dom"),
    ("lerni",     "to learn",       "uczyć się"),
    ("paroli",    "to speak",       "mówić"),
    ("ridi",      "to laugh",       "śmiać się"),
    ("frato",     "brother",        "brat"),
]

_ATTRACT_QUIZ_INTROS = [
    ("Co znaczy po esperanto słowo:  ", "pl"),
    ("What does this Esperanto word mean?  ", "en"),
    ("Zgadnij — co to po esperanto?  ", "pl"),
    ("Quick quiz — can you guess what this word means?  ", "en"),
    ("Mam dla ciebie zagadkę! Co znaczy:  ", "pl"),
    ("Here's a fun one — what does this mean in Esperanto?  ", "en"),
]

_ATTRACT_MUSIC_INTROS = [
    ("A teraz posłuchaj fragmentu muzyki esperanto!", "pl"),
    ("Now listen to a snippet of real Esperanto music!", "en"),
    ("Muzyka też może być po esperanto — posłuchaj!", "pl"),
    ("Esperanto even has its own music scene — listen to this!", "en"),
    ("Oto próbka muzyki w języku esperanto. Czy zgadniesz tytuł?", "pl"),
    ("Can you guess the title of this Esperanto song?", "en"),
]

_ATTRACT_POEM_INTROS = [
    ("A teraz posłuchaj fragmentu poezji esperanto!", "pl"),
    ("Now — a snippet of Esperanto poetry!", "en"),
    ("Esperanto ma bogatą tradycję poetycką. Posłuchaj!", "pl"),
    ("Esperanto poetry has been written for over 130 years. Here's a taste!", "en"),
]

_ATTRACT_FACTS = [
    ("Esperanto jest tak regularny, że nie ma ani jednego wyjątku gramatycznego!", "pl"),
    ("Every Esperanto noun ends in -o, every adjective in -a, every verb infinitive in -i!", "en"),
    ("W esperanto wszystkie rzeczowniki kończą się na -o, a przymiotniki na -a. Proste!", "pl"),
    ("The word 'Esperanto' literally means 'one who hopes' — from the root espero, hope!", "en"),
    ("Esperanto ma własne hymny, literaturę, a nawet filmy — w tym horror z 1966 roku!", "pl"),
    ("There are native Esperanto speakers — children raised speaking it from birth!", "en"),
    ("Google Translate obsługuje esperanto! Możesz ćwiczyć w telefonie!", "pl"),
    ("Duolingo has an Esperanto course with millions of learners worldwide!", "en"),
]

_ATTRACT_CTAS = [
    ("Naciśnij dowolny przycisk żeby zacząć! Sprawdź też laminowaną instrukcję obok robota.", "pl"),
    ("Press any button to start exploring! Check the laminated guide next to me.",             "en"),
    ("Chcesz spróbować? Naciśnij przycisk i wybierz tryb!",                                   "pl"),
    ("Ready to try? Hit any button and pick a mode — I'll guide you!",                        "en"),
    ("Śmiało! Naciśnij przycisk — robot czeka na Ciebie!",                                    "pl"),
    ("Go ahead — press a button and let's explore Esperanto together!",                       "en"),
]

_ATTRACT_GOODBYES = [
    ("Wróć kiedy chcesz! Do zobaczenia!", "pl"),
    ("Come back anytime! See you soon!",  "en"),
    ("Żal mi, że odchodzisz... Wróć po więcej esperanto!",      "pl"),
    ("Aw, don't go! Come back to learn more Esperanto soon!",   "en"),
    ("Adiaŭ! To znaczy 'do widzenia' po esperanto. Wróć!",       "pl"),
    ("Adiaŭ — that means goodbye in Esperanto. Come back soon!", "en"),
]

_ATTRACT_SEQ_TYPES = ["word_quiz", "music_snippet", "poem_snippet", "fun_fact", "full"]


class AttractMode(Mode):
    """
    Mode 4 — Attract / Showcase (WRO Area 3).
    Picks one of 5 sequence types without immediate repeats.
    """
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

    def _speak_teaser_word(self, word: str, en_meaning: str, pl_meaning: str):
        """Speak word via phonetic PL TTS, then its meaning in UI language only."""
        _speak(word, lang="eo")
        if UI_LANG == "pl":
            _speak(f"To znaczy: {pl_meaning}!", lang="pl")
        else:
            _speak(f"It means: {en_meaning}!", lang="en")

    # ---- sequence types ----

    def _seq_word_quiz(self):
        text, lang = self._pick_greeting()
        _speak(text, lang=lang)
        if self._stop_flag: return

        intro_text, intro_lang = random.choice(_ATTRACT_QUIZ_INTROS)
        word, en_meaning, pl_meaning = random.choice(_ATTRACT_TEASER_WORDS)
        _speak(intro_text, lang=intro_lang)
        # Speak word via phonetic PL TTS
        _speak(word, lang="eo")
        if self._sleep_check(2.5): return
        # Reveal answer in UI language only
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
            if UI_LANG == "pl":
                answer = f"To był: {title}"
                if artist:
                    answer += f" — {artist}."
                _speak(answer, lang="pl")
            else:
                answer = f"That was: {title}"
                if artist:
                    answer += f" — {artist}."
                _speak(answer, lang="en")
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
            if UI_LANG == "pl":
                answer = f"To był: {title}"
                if author:
                    answer += f" — {author}."
                _speak(answer, lang="pl")
            else:
                answer = f"That was: {title}"
                if author:
                    answer += f" — {author}."
                _speak(answer, lang="en")
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

        # Bonus: one vocabulary word via phonetic PL TTS
        word, en_meaning, pl_meaning = random.choice(_ATTRACT_TEASER_WORDS)
        if UI_LANG == "pl":
            _speak("A przy okazji — słowo", lang="pl")
            _speak(word, lang="eo")
            _speak(f"znaczy: {pl_meaning}!", lang="pl")
        else:
            _speak("And here's a bonus word:", lang="en")
            _speak(word, lang="eo")
            _speak(f"It means: {en_meaning}!", lang="en")
        if self._stop_flag: return

        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _seq_full(self):
        text, lang = self._pick_greeting()
        _speak(text, lang=lang)
        if self._stop_flag: return

        # quiz
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

        # muzika or poetry
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

        # fun fact
        fact_text, fact_lang = random.choice(_ATTRACT_FACTS)
        _speak(fact_text, lang=fact_lang)
        if self._stop_flag: return

        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _run_sequence(self):
        self._speaking = True
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
        _speak(
            "Welcome! I'm an Esperanto robot. "
            "I have four modes: Flashcards, Poems, Music, and AI Conversation. "
            "Press and hold the left button to open the menu and pick a mode. "
            "Check the laminated card next to me for the full guide. Enjoy!",
            lang="en"
        )
        _speak(
            "Cześć! Jestem robotem esperanto. "
            "Mam cztery tryby: Fiszki, Poezja, Muzyka i Rozmowa z AI. "
            "Przytrzymaj lewy przycisk żeby otworzyć menu. "
            "Sprawdź też laminowaną instrukcję obok. Miłej zabawy!",
            lang="pl"
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
        self._stop_sequence()
        ACTIVITY.poke()
        for _ in range(40):
            if not self._speaking:
                break
            time.sleep(0.1)
        _tts_stop_event.clear()
        self._speak_instructions()

    def on_action_hold(self):
        pass

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

    def on_attract_timeout(self):
        self.on_attract_lost()

    def tick(self):
        pass

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
        # Pre-load track lists so AttractMode can play snippets immediately,
        # even before the user manually enters Music/Poems mode.
        _music_mode.preload_entries()
        _poems_mode.preload_entries()
        self._fc_mode = _fc_mode
        self._a0_mode = _a0_mode
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
        print(f"[MGR] {old} → {self.current.name}")
        self.current.on_enter()

    def handle(self, signal: str):
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
            if hasattr(self.current, "paused"):
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.pause()
                    self.current.paused = True
                    print("[MGR] Media paused (menu open)")
        elif signal == "MEDIA_RESUME":
            if hasattr(self.current, "paused") and self.current.paused:
                pygame.mixer.music.unpause()
                self.current.paused = False
                print("[MGR] Media resumed")
        elif signal.startswith("FILTER:"):
            unit = signal.split(":", 1)[1].strip()
            self._fc_mode.set_filter(unit if unit.lower() != "none" else None)
            print(f"[MGR] Filter → {unit!r} — switching to FLASHCARDS")
            self.switch_to(0)
        elif signal == "LESSON_FILTER:Technology":
            self._fc_mode.set_filter("Technology")
            _speak_ui(
                "Now drill those words in Flashcards! Switching to Technology filter.",
                "Teraz ćwicz te słowa w Fiszkach! Przełączam na filtr Technologia.",
            )
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
# MAIN
# ============================================================

def _hub_reader(stdout, q: queue.Queue):
    for line in stdout:
        line = line.strip()
        if line:
            q.put(line)
    q.put(None)


def _preload_models(manager: "ModeManager"):
    """Eagerly load Whisper and wav2vec2 in background threads at startup.

    This avoids the multi-minute cold-start delay the first time Conversation
    mode is entered.  Models are loaded into the ConversationMode instance that
    already exists inside the manager, so on_enter() finds them ready.
    """
    conv: ConversationMode = manager.modes[3]  # type: ignore[assignment]
    threading.Thread(target=conv._get_whisper,   daemon=True, name="preload-whisper").start()
    threading.Thread(target=conv._get_wav2vec2,  daemon=True, name="preload-wav2vec2").start()
    print("[BOOT] Model preload started in background (Whisper + wav2vec2).")


def _fmt_entry(i: int, entry: dict, current_idx: int) -> str:
    marker = "▶" if i == current_idx else " "
    title  = entry.get("title") or entry.get("filename", "?")
    artist = entry.get("artist") or entry.get("author", "")
    plays  = entry.get("play_count", 0)
    rating = ("★" * entry["rating"] if entry.get("rating") else "  ") if entry.get("rating") else ""
    detail = f"  {artist}" if artist else ""
    return f"  {marker} {i+1:>3}. {title}{detail}  [{plays}x]{('  ' + rating) if rating else ''}"


def _show_media_list(mode: MediaMode) -> None:
    """Print a numbered track list for a MediaMode."""
    if not mode.entries:
        print(f"[TUI] {mode.name}: no tracks loaded (folder empty or JSON missing).")
        return
    print(f"\n── {mode.name} ({len(mode.entries)} tracks) " + "─" * 30)
    for i, e in enumerate(mode.entries):
        print(_fmt_entry(i, e, mode.index))
    print("─" * 50)
    print("  Type a number to jump to that track.\n")


def _tui_music(manager: "ModeManager"):
    """
    Sub-TUI for MUSIC mode (mode 2).

    Commands:
      list / l          — show track list
      <number>          — jump to track N
      s / stop          — stop playback
      r / random        — random track
      now               — currently playing
      back / b          — return to main TUI
    """
    print("\n[MUSIC] Entering music control. 'list' to see tracks, 'back' to return.\n")
    manager.switch_to(2)
    mode = manager._music_mode

    while True:
        try:
            raw = input("[music]> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            continue
        cmd = raw.lower()

        if cmd in ("list", "l"):
            _show_media_list(mode)
        elif cmd in ("s", "stop"):
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
            print("[MUSIC] Stopped.")
        elif cmd in ("r", "random"):
            if mode.entries:
                idx = random.randint(0, len(mode.entries) - 1)
                mode.jump_to(idx)
                print(f"[MUSIC] ▶ {mode.entries[idx].get('title') or mode.entries[idx]['filename']}")
            else:
                print("[MUSIC] No tracks loaded.")
        elif cmd == "now":
            if mode.playing and mode.entries:
                e = mode.entries[mode.index]
                title  = e.get("title") or e["filename"]
                artist = e.get("artist") or e.get("author", "")
                plays  = e.get("play_count", 0)
                print(f"[MUSIC] ▶ {title}" + (f"  — {artist}" if artist else "") + f"  [{plays}x]")
            else:
                print("[MUSIC] Nothing playing.")
        elif cmd in ("back", "b"):
            print("[MUSIC] Back to main TUI.")
            break
        elif cmd.isdigit():
            n = int(cmd)
            if 1 <= n <= len(mode.entries):
                mode.jump_to(n - 1)
                print(f"[MUSIC] ▶ {mode.entries[n-1].get('title') or mode.entries[n-1]['filename']}")
            else:
                print(f"[MUSIC] Out of range (1–{len(mode.entries)}).")
        else:
            print(f"[MUSIC] Unknown: {raw!r}  (list | <n> | stop | random | now | back)")


def _tui_poems(manager: "ModeManager"):
    """
    Sub-TUI for POEMS mode (mode 1).

    Commands:
      list / l          — show poem list
      <number>          — jump to poem N
      s / stop          — stop playback
      r / random        — random poem
      now               — currently playing
      back / b          — return to main TUI
    """
    print("\n[POEMS] Entering poems control. 'list' to see poems, 'back' to return.\n")
    manager.switch_to(1)
    mode = manager._poems_mode

    while True:
        try:
            raw = input("[poems]> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            continue
        cmd = raw.lower()

        if cmd in ("list", "l"):
            _show_media_list(mode)
        elif cmd in ("s", "stop"):
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
            print("[POEMS] Stopped.")
        elif cmd in ("r", "random"):
            if mode.entries:
                idx = random.randint(0, len(mode.entries) - 1)
                mode.jump_to(idx)
                e = mode.entries[idx]
                title  = e.get("title") or e["filename"]
                author = e.get("author") or e.get("artist", "")
                print(f"[POEMS] ▶ {title}" + (f"  — {author}" if author else ""))
            else:
                print("[POEMS] No poems loaded.")
        elif cmd == "now":
            if mode.playing and mode.entries:
                e = mode.entries[mode.index]
                title  = e.get("title") or e["filename"]
                author = e.get("author") or e.get("artist", "")
                plays  = e.get("play_count", 0)
                print(f"[POEMS] ▶ {title}" + (f"  — {author}" if author else "") + f"  [{plays}x]")
            else:
                print("[POEMS] Nothing playing.")
        elif cmd in ("back", "b"):
            print("[POEMS] Back to main TUI.")
            break
        elif cmd.isdigit():
            n = int(cmd)
            if 1 <= n <= len(mode.entries):
                mode.jump_to(n - 1)
                e = mode.entries[n - 1]
                title  = e.get("title") or e["filename"]
                author = e.get("author") or e.get("artist", "")
                print(f"[POEMS] ▶ {title}" + (f"  — {author}" if author else ""))
            else:
                print(f"[POEMS] Out of range (1–{len(mode.entries)}).")
        else:
            print(f"[POEMS] Unknown: {raw!r}  (list | <n> | stop | random | now | back)")


def _terminal_tui(manager: "ModeManager"):
    """
    Main interactive terminal — runs in a background thread.

    Top-level commands:
      music / m         — enter Music sub-TUI  (mode 2)
      poems / p         — enter Poems sub-TUI  (mode 1)
      fc / flashcards   — switch to Flashcards (mode 0)
      conv / c          — switch to Conversation (mode 3)
      attract / a       — switch to Attract demo (mode 4)
      lesson / l        — switch to A0 Lesson (mode 5)
      mode <n>          — switch to mode n directly
      sleep             — send robot to sleep
      filter <unit>     — set flashcard unit filter (e.g.  filter Technology)
      filter clear      — clear flashcard filter
      status            — show current mode and hub state
      q / quit          — exit TUI (robot keeps running)
      ? / help          — show this help
    """
    _HELP = (
        "\n[TUI] Commands:\n"
        "  music / m          — Music sub-TUI (track list, jump, stop, random)\n"
        "  poems / p          — Poems sub-TUI (same controls, separate context)\n"
        "  fc / flashcards    — switch to Flashcards mode\n"
        "  conv / c           — switch to Conversation mode\n"
        "  attract / a        — switch to Attract / showcase mode\n"
        "  lesson / l         — switch to A0 Lesson mode\n"
        "  mode <n>           — switch to mode n directly (0-5)\n"
        "  sleep              — put robot to sleep\n"
        "  filter <unit>      — set flashcard filter  (e.g. filter Technology)\n"
        "  filter clear       — clear flashcard filter\n"
        "  status             — show current mode and playback state\n"
        "  q / quit           — exit TUI (robot keeps running)\n"
        "  ? / help           — show this help\n"
    )

    print("\n[TUI] Terminal control active. Type 'help' for commands.\n")

    while True:
        try:
            raw = input("[tui]> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            continue
        cmd = raw.lower()
        parts = cmd.split()

        if cmd in ("?", "help"):
            print(_HELP)

        # ── Media sub-TUIs ───────────────────────────────────────
        elif parts[0] in ("music", "m"):
            _tui_music(manager)

        elif parts[0] in ("poems", "poem", "p"):
            _tui_poems(manager)

        # ── Direct mode switches ─────────────────────────────────
        elif parts[0] in ("fc", "flashcards"):
            manager.switch_to(0)
            print("[TUI] → Flashcards mode.")

        elif parts[0] in ("conv", "c", "conversation"):
            manager.switch_to(3)
            print("[TUI] → Conversation mode.")

        elif parts[0] in ("attract", "a"):
            manager.switch_to(4)
            print("[TUI] → Attract mode.")

        elif parts[0] in ("lesson", "a0"):
            manager.switch_to(5)
            print("[TUI] → A0 Lesson mode.")

        elif parts[0] == "mode":
            if len(parts) == 2 and parts[1].isdigit():
                manager.switch_to(int(parts[1]))
                print(f"[TUI] → mode {parts[1]}.")
            else:
                print("[TUI] Usage: mode <0-5>")

        # ── Sleep ────────────────────────────────────────────────
        elif cmd == "sleep":
            manager.handle("SLEEP")
            print("[TUI] Robot sent to sleep.")

        # ── Flashcard filter ─────────────────────────────────────
        elif parts[0] == "filter":
            if len(parts) < 2:
                current = manager._fc_mode.active_filter or "(none)"
                print(f"[TUI] Current filter: {current}  — usage: filter <unit> | filter clear")
            elif parts[1] == "clear":
                manager._fc_mode.set_filter(None)
                print("[TUI] Flashcard filter cleared.")
            else:
                unit = " ".join(raw.split()[1:])   # preserve original case
                manager._fc_mode.set_filter(unit)
                print(f"[TUI] Flashcard filter → {unit!r}")

        # ── Status ───────────────────────────────────────────────
        elif cmd == "status":
            mode = manager.current
            sleeping = manager._sleeping
            print(f"[TUI] Mode: {mode.name}  |  Sleeping: {sleeping}")
            for m in (manager._music_mode, manager._poems_mode):
                if m.playing and m.entries:
                    e = m.entries[m.index]
                    title = e.get("title") or e["filename"]
                    print(f"[TUI] Playing [{m.name}]: {title}")

        # ── Quit ─────────────────────────────────────────────────
        elif cmd in ("q", "quit"):
            print("[TUI] Exiting terminal control.")
            break

        else:
            print(f"[TUI] Unknown command: {raw!r}  (type 'help')")


def main():
    os.chdir(BASE_DIR)
    pygame.init()
    _start_mic_monitor()

    manager = ModeManager()
    _preload_models(manager)

    # Start interactive terminal TUI in background (non-blocking)
    threading.Thread(
        target=_terminal_tui, args=(manager,), daemon=True, name="terminal-tui"
    ).start()

    MAX_CONNECT_RETRIES = 3
    connect_failures    = 0

    while True:
        attempt_str = f"[attempt {connect_failures + 1}/{MAX_CONNECT_RETRIES}]" \
                      if connect_failures > 0 else ""
        print(f"Starting hub connection... (Ctrl+C to quit) {attempt_str}".strip())

        process = subprocess.Popen(
            [PYTHON, "-m", "pybricksdev", "run", "ble", "--wait", "hub.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        threading.Thread(
            target=_hub_reader,
            args=(process.stdout, _signal_queue),
            daemon=True
        ).start()

        connected = False
        while True:
            try:
                line = _signal_queue.get(timeout=30)
            except queue.Empty:
                print("[ERR] Timeout — hub did not send READY within 30s.")
                break
            if line is None:
                break
            print(f"[hub] {line}")
            if line == "READY":
                connected = True
                break

        if not connected:
            connect_failures += 1
            process.terminate()
            if connect_failures >= MAX_CONNECT_RETRIES:
                print(f"\n[ERR] Hub did not connect after {MAX_CONNECT_RETRIES} attempts.")
                print("[ERR] Checklist:")
                print("  1. Hub is powered on (press center button)")
                print("  2. Pybricks firmware installed (code.pybricks.com)")
                print("  3. Bluetooth enabled on this PC")
                print("  4. hub.py has no syntax errors")
                sys.exit(1)
            print(f"[ERR] Retrying in 3s... ({connect_failures}/{MAX_CONNECT_RETRIES})")
            time.sleep(3)
            continue

        connect_failures = 0
        print("[OK] Hub connected. Waiting for signals...")

        while True:
            try:
                line = _signal_queue.get(timeout=0.05)
            except queue.Empty:
                manager.tick()
                continue

            if line is None:
                print("[ERR] Hub disconnected — reconnecting in 3s...")
                break

            if any(s in line for s in ("SystemExit", "Traceback", "program was")):
                print(f"[hub-sys] {line}")
                break

            print(f"[hub] {line}")
            manager.handle(line)
            manager.tick()

        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        time.sleep(3)


if __name__ == "__main__":
    main()