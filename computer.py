"""
WRO2026 — Esperanto Flashcard Robot
computer.py — main PC logic

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
    "inactivity_timeout_s":  60,
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


def _speak(text: str, lang: str = "en"):
    global _speaking
    try:
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
    except Exception as e:
        print(f"[TTS] Error: {e}")

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

    def __init__(self):
        self.words:   list = []
        self.current: dict = {}
        self.shown_definition = False
        # H5: statystyki sesji — mówione przy wyjściu z trybu
        self.session_correct: int = 0
        self.session_wrong:   int = 0

    def on_enter(self):
        with open(WORDS_FILE, encoding="utf-8") as f:
            self.words = json.load(f)
        print("[FC] Wordlist loaded.")
        # H5: reset liczników przy każdym wejściu w tryb
        self.session_correct = 0
        self.session_wrong   = 0
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
        ACTIVITY.poke()
        sr_update(self.current, True)
        self._save()
        self.session_correct += 1   # H5
        self._next()

    def on_no(self):
        ACTIVITY.poke()
        sr_update(self.current, False)
        self._save()
        self.session_wrong += 1     # H5
        if not self.shown_definition:
            self.shown_definition = True
            self._speak_definition()
        self._next()

    def on_action_hold(self):
        ACTIVITY.poke()
        self.shown_definition = True
        self._speak_definition()

    def _speak_session_summary(self):
        """H5: Mówione podsumowanie sesji — dowód autonomicznej analizy danych."""
        total = self.session_correct + self.session_wrong
        if total == 0:
            return
        weak = max(self.words, key=lambda w: w.get("wrong_count", 0), default=None)
        summary = (
            f"Session summary: {self.session_correct} correct, "
            f"{self.session_wrong} wrong out of {total} cards."
        )
        if weak and weak.get("wrong_count", 0) > 0:
            summary += f" Weakest word: {weak['word']}."
        print(f"[FC] {summary}")
        _speak(summary, lang="en")
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

    def on_enter(self):
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

        self.entries = valid
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
        if was_playing:
            pygame.mixer.music.pause()
        entry = self.entries[self.index] if self.entries else {}
        info  = build_info_speech(entry)
        print(f"[{self.name}] INFO: {info}")
        _speak(info, lang="en")
        if was_playing:
            pygame.mixer.music.unpause()
            self.paused = False

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
    """Call Groq via official SDK (avoids Cloudflare 1010 that blocks urllib)."""
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
        # Fallback: raw HTTPS with proper browser-like headers
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
        self._pending_media_offer: bool = False   # Punkt 2

    @property
    def difficulty(self) -> str:
        return _DIFFICULTY_LABELS[self.difficulty_idx]

    @property
    def system_prompt(self) -> str:
        return _CONV_SYSTEM_PROMPTS[self.difficulty]

    def _cycle_difficulty(self):
        self.difficulty_idx = (self.difficulty_idx + 1) % len(_DIFFICULTY_LABELS)
        print(f"[CONV] Difficulty → {self.difficulty}")
        _speak(f"Nivelo {self.difficulty}", lang="en")

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
        """Lazy-load wav2vec2 fine-tuned na esperanto (cpierse/wav2vec2-large-xlsr-53-esperanto)."""
        if self._wav2vec2_model is None:
            try:
                from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
                model_id = "cpierse/wav2vec2-large-xlsr-53-esperanto"
                print(f"[CONV] Loading wav2vec2 esperanto model (first run: ~1GB download)...")
                self._wav2vec2_processor = Wav2Vec2Processor.from_pretrained(model_id)
                self._wav2vec2_model     = Wav2Vec2ForCTC.from_pretrained(model_id)
                self._wav2vec2_model.eval()
                print("[CONV] wav2vec2 esperanto ready.")
            except Exception as e:
                print(f"[CONV] wav2vec2 load failed: {e}")
                self._wav2vec2_model = None
        return self._wav2vec2_model

    def _transcribe_wav2vec2(self, audio: np.ndarray) -> str:
        """Transkrybuj audio używając wav2vec2 fine-tuned na esperanto."""
        import torch
        model     = self._get_wav2vec2()
        processor = self._wav2vec2_processor
        if model is None:
            return ""
        try:
            # wav2vec2 oczekuje float32 w zakresie [-1, 1] przy 16kHz
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

            # Próbuj wav2vec2 (fine-tuned na esperanto) — główny STT
            user_text = self._transcribe_wav2vec2(audio)

            # Fallback: Whisper jeśli wav2vec2 niedostępny lub pusty
            if not user_text:
                whisper = self._get_whisper()
                if whisper is None:
                    _speak("Pardonu, mi ne povas aŭdi.", lang="en")
                    return
                audio_float = audio.astype(np.float32) / 32768.0
                segments, info = whisper.transcribe(audio_float, language=None)  # H4: autodetekcja zamiast "it"
                print(f"[CONV] Whisper fallback STT lang={info.language} conf={info.language_probability:.0%}")
                user_text = " ".join(seg.text.strip() for seg in segments).strip()

            if not user_text:
                print("[CONV] No speech detected.")
                _speak("Mi ne aŭdis vin. Bonvolu paroli denove.", lang="en")
                return

            print(f"[CONV] User said: {user_text!r}")
            self.history.append({"role": "user", "content": user_text})

            max_turns = CFG["conv_history_turns"] * 2
            if len(self.history) > max_turns:
                self.history = self.history[-max_turns:]

            api_key = CFG.get("groq_api_key", "")
            if not api_key:
                print("[CONV] No GROQ_API_KEY set!")
                _speak("Mankas la API-ŝlosilo. Bonvolu agordi config.json.", lang="en")
                return

            reply = _groq_chat(history=self.history, system=self.system_prompt,
                               api_key=api_key, model=CFG["groq_model"])
            print(f"[CONV] Robot: {reply!r}")
            self.history.append({"role": "assistant", "content": reply})

            # Punkt 2: kontekstowe przejście do POEMS/MUSIC
            # Jeśli odpowiedź LLM dotyczy kultury esperanto — zaproponuj media
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
                _speak(reply_with_offer, lang="en")
            else:
                self._pending_media_offer = False
                _speak(reply, lang="en")

        finally:
            with self._lock:
                self._recording = False

    def on_enter(self):
        self.history = []
        self._pending_media_offer = False   # Punkt 2: reset przy wejściu
        if not CFG.get("groq_api_key"):
            print("[CONV] WARNING: groq_api_key not set.")
        print(f"[CONV] Ready. Difficulty: {self.difficulty}. Press YES to speak.")
        _speak("Saluton! Mi estas via esperanto-konversaciisto. "
               "Premu la dekstran butonon por paroli.", lang="en")
        # Preload wav2vec2 w tle (pierwsze uruchomienie pobiera ~1GB)
        threading.Thread(target=self._get_wav2vec2, daemon=True).start()
        threading.Thread(target=self._get_whisper, daemon=True).start()

    def on_yes(self):
        ACTIVITY.poke()
        # Punkt 2: jeśli była oferta mediów — przejdź do POEMS (1) lub MUSIC (2)
        if self._pending_media_offer:
            self._pending_media_offer = False
            target = random.choice([1, 2])
            print(f"[CONV] Media offer accepted → MODE:{target}")
            print(f"MODE:{target}")   # sygnał do ModeManagera
            return
        threading.Thread(target=self._listen_and_reply, daemon=True).start()

    def on_no(self):
        ACTIVITY.poke()
        self._pending_media_offer = False   # Punkt 2: anuluj ofertę
        with self._lock:
            if self._recording:
                print("[CONV] Cancelling current turn.")
                return
        self.history = []
        print("[CONV] History cleared.")
        _speak("Konversacio rekomencita.", lang="en")

    def on_action_hold(self):
        ACTIVITY.poke()
        self._cycle_difficulty()

    def on_sleep(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

    def on_wake(self):
        _speak("Saluton denove!", lang="en")

# ============================================================
# ATTRACT MODE  (Mode 4 — WRO Obszar 3)
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
    ("kanti",     "to sing",        "śpiewać"),
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

# Typy sekwencji attract — losowane żeby nie było powtórzeń
_ATTRACT_SEQ_TYPES = ["word_quiz", "music_snippet", "poem_snippet", "fun_fact", "full"]


class AttractMode(Mode):
    """
    Mode 4 — Attract / Showcase (WRO Obszar 3).
    Losuje jeden z 5 typów sekwencji: quiz słówka, muzyka, poezja, ciekawostka, pełna.
    Nie przerywa sekwencji gdy ktoś odchodzi — kończy, potem gra pożegnanie.
    """
    name = "ATTRACT"

    def __init__(self, music_mode: MediaMode, poems_mode: MediaMode):
        self._music          = music_mode
        self._poems          = poems_mode
        self._active         = False
        self._stop_flag      = False
        self._speaking       = False   # True podczas sekwencji — hub nie śpi
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
        """Losuj typ sekwencji bez powtórzenia z poprzedniej."""
        choices = [t for t in _ATTRACT_SEQ_TYPES if t != self._last_seq_type]
        t = random.choice(choices)
        self._last_seq_type = t
        return t

    def _sleep_check(self, seconds: float) -> bool:
        """Czeka podaną liczbę sekund, sprawdzając stop_flag co 0.1s. Zwraca True jeśli przerwano."""
        steps = int(seconds / 0.1)
        for _ in range(steps):
            if self._stop_flag:
                return True
            time.sleep(0.1)
        return False

    def _play_snippet(self, entries: list, directory, duration_s: int = 10) -> dict | None:
        """Gra losowy fragment z listy przez duration_s sekund. Zwraca entry lub None."""
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

    # ---- typy sekwencji ----

    def _seq_word_quiz(self):
        """Powitanie + quiz słówkowy z dramatyczną pauzą."""
        text, lang = self._pick_greeting()
        _speak(text, lang=lang)
        if self._stop_flag: return

        intro_text, intro_lang = random.choice(_ATTRACT_QUIZ_INTROS)
        word, en_meaning, pl_meaning = random.choice(_ATTRACT_TEASER_WORDS)
        _speak(intro_text + word, lang=intro_lang)
        if self._sleep_check(2.5): return

        _speak(f"It means: {en_meaning}!", lang="en")
        _speak(f"Po polsku: {pl_meaning}!", lang="pl")
        if self._stop_flag: return

        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _seq_music_snippet(self):
        """Powitanie + 12s fragment muzyki + tytuł + CTA."""
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
            answer = f"To był: {title}" if random.random() < 0.5 else f"That was: {title}"
            lang_a = "pl" if "był" in answer else "en"
            if artist:
                answer += f" — {artist}."
            _speak(answer, lang=lang_a)
        if self._stop_flag: return

        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _seq_poem_snippet(self):
        """Powitanie + 12s fragment poezji + tytuł + CTA."""
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
            answer = f"To był: {title}" if random.random() < 0.5 else f"That was: {title}"
            lang_a = "pl" if "był" in answer else "en"
            if author:
                answer += f" — {author}."
            _speak(answer, lang=lang_a)
        if self._stop_flag: return

        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _seq_fun_fact(self):
        """Ciekawostka o esperanto + quiz słówkowy + CTA."""
        text, lang = self._pick_greeting()
        _speak(text, lang=lang)
        if self._stop_flag: return

        fact_text, fact_lang = random.choice(_ATTRACT_FACTS)
        _speak(fact_text, lang=fact_lang)
        if self._stop_flag: return

        # bonus: jedno słówko
        word, en_meaning, pl_meaning = random.choice(_ATTRACT_TEASER_WORDS)
        _speak(f"A przy okazji — '{word}' znaczy '{pl_meaning}'!", lang="pl")
        if self._stop_flag: return

        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _seq_full(self):
        """Pełna sekwencja: powitanie + quiz + muzyka + ciekawostka + CTA."""
        text, lang = self._pick_greeting()
        _speak(text, lang=lang)
        if self._stop_flag: return

        # quiz
        intro_text, intro_lang = random.choice(_ATTRACT_QUIZ_INTROS)
        word, en_meaning, pl_meaning = random.choice(_ATTRACT_TEASER_WORDS)
        _speak(intro_text + word, lang=intro_lang)
        if self._sleep_check(2.5): return
        _speak(f"It means: {en_meaning}!", lang="en")
        _speak(f"Po polsku: {pl_meaning}!", lang="pl")
        if self._stop_flag: return

        # muzyka lub poezja
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

        # ciekawostka
        fact_text, fact_lang = random.choice(_ATTRACT_FACTS)
        _speak(fact_text, lang=fact_lang)
        if self._stop_flag: return

        cta_text, cta_lang = random.choice(_ATTRACT_CTAS)
        _speak(cta_text, lang=cta_lang)

    def _run_sequence(self):
        self._speaking = True
        print("ATTRACT_SPEAKING")   # hub: nie śpij
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
            print("ATTRACT_IDLE")   # hub: możesz liczyć timeout

    def _loop(self):
        while self._active and not self._stop_flag:
            self._run_sequence()
            # Pauza 25s między sekwencjami
            for _ in range(250):
                if not self._active or self._stop_flag:
                    return
                time.sleep(0.1)

    def on_enter(self):
        self._stop_flag = False
        self._active    = True
        print("[ATTRACT] Active.")
        threading.Thread(target=self._loop, daemon=True).start()

    def _stop_sequence(self):
        self._active    = False
        self._stop_flag = True
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
        self._speak_instructions()

    def on_no(self):
        self._stop_sequence()
        ACTIVITY.poke()
        self._speak_instructions()

    def on_action_hold(self):
        pass

    def on_sleep(self):
        self._stop_sequence()

    def on_wake(self):
        if not self._active:
            self.on_enter()

    def on_attract_lost(self):
        """Ktoś odszedł — czekaj aż sekwencja się skończy, potem pożegnanie."""
        # Nie przerywaj _stop_sequence — pozwól dokończyć bieżącą sekwencję
        self._active = False   # pętla _loop nie zacznie nowej sekwencji
        # Pożegnanie zostanie zagrane przez _loop po zakończeniu aktualnej sekwencji
        threading.Thread(target=self._goodbye_then_sleep, daemon=True).start()

    def _goodbye_then_sleep(self):
        """Czeka aż _speaking=False, gra pożegnanie, idzie spać."""
        # Czekaj max 60s aż bieżąca sekwencja dobiegnie końca
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
        """Hub zgłosił że nikogo nie ma — obsługuj jak on_attract_lost."""
        self.on_attract_lost()

    def tick(self):
        pass

# ============================================================
# MODE MANAGER
# ============================================================

class ModeManager:
    def __init__(self):
        _music_mode = MediaMode(MUSIC_DIR, "MUSIC", "music.json")
        _poems_mode = MediaMode(POEMS_DIR, "POEMS", "poems.json")
        self.modes: list[Mode] = [
            FlashcardsMode(),
            _poems_mode,
            _music_mode,
            ConversationMode(),
            AttractMode(_music_mode, _poems_mode),
        ]
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
            # H5: jeśli opuszczamy FlashcardsMode — najpierw powiedz podsumowanie
            if isinstance(self.current, FlashcardsMode):
                self.current._speak_session_summary()
            if hasattr(self.current, "_stop_sequence"):
                self.current._stop_sequence()
            elif hasattr(self.current, "_stop"):
                self.current._stop()
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
            pass  # hub otwiera menu sam
        elif signal in ("ATTRACT_SPEAKING", "ATTRACT_IDLE"):
            pass  # sygnały dla huba — ignoruj na PC
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


def main():
    os.chdir(BASE_DIR)
    pygame.init()
    _start_mic_monitor()

    manager = ModeManager()

    MAX_CONNECT_RETRIES = 3   # ile razy próbować READY przed wyjściem
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

        # Czekaj na READY
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

        # Połączono — resetuj licznik
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
        time.sleep(3)
        # Po rozłączeniu podczas pracy — nie zliczaj do MAX_CONNECT_RETRIES


if __name__ == "__main__":
    main()