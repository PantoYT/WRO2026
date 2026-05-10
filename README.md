# 🤖 Espero-bot — WRO 2026 Future Innovators

> *People love physical things. Learning through play is fun. Why not combine them to teach a language that could unite the world?*

---

## The Idea

Esperanto is the only widely spoken planned language designed from the ground up so that **no nation has an advantage** — no native speaker gets a head start, no culture dominates. Created in 1887 by Ludwig Zamenhof in Warsaw, it has been spoken by an estimated 2 million people across 130+ years. Yet access to quality learning materials remains scattered and unequal.

At the same time, physical interaction is one of the most effective ways to learn. Flashcards have been shown to outperform passive reading. Robots invite curiosity. Music and poetry make language feel alive.

**Our robot combines all of these.** It teaches Esperanto words through spaced repetition, plays real Esperanto poetry and music from its digital archive, holds a live AI conversation in the language — and actively invites passersby to engage with a culture that belongs to everyone.

This is not just a robot. It is a **portable cultural archive and language teacher in one device**, designed to work entirely offline for core functions.

---

## WRO 2026 Theme: Robots Meet Culture

The project addresses all three challenge areas:

| Area | How this robot responds |
|---|---|
| **Area 1 — Preserving cultural heritage** | `wordlist.json` is a growing digital dictionary of Esperanto. `poems.json` and `music.json` are structured archives of Esperanto poetry and music — a language with no state institution to preserve it. |
| **Area 2 — Human–robot–AI co-creation** | `ConversationMode` is a real dialogue partner: the LLM adapts its language level to each speaker in real time. It also detects cultural keywords and proactively offers to play related media. |
| **Area 3 — Experiencing culture through robots** | `AttractMode` actively approaches passersby with greetings, word quizzes, music snippets and poetry in Esperanto — the robot comes to people, not the other way around. |

**UN SDGs supported:** SDG 4 (Quality Education), SDG 11 (Sustainable Cities and Cultural Heritage), SDG 17 (Partnerships for the Goals — technology + cultural heritage + education in one device).

---

## Architecture

```
┌─────────────────────────────────────────┐
│           LEGO SPIKE Prime (hub.py)     │
│                                         │
│  Ultrasonic sensor (A) → detect presence│
│  Scanning motor    (B) → sweep ±45°     │
│  Flag motor        (D) → wave flag      │
│  ForceSensor LEFT  (E) → NO / menu      │
│  ForceSensor RIGHT (F) → YES / action   │
│  5×5 LED matrix        → mode display   │
│  Speaker               → beeps & tones  │
└──────────────┬──────────────────────────┘
               │  Bluetooth BLE (pybricksdev)
               │  hub prints signals → PC reads
               ▼
┌─────────────────────────────────────────┐
│            PC / Steam Deck (computer.py)│
│                                         │
│  SM-2 algorithm     → flashcard order   │
│  Adaptive queue     → media selection   │
│  wav2vec2 (local)   → Esperanto STT     │
│  faster-whisper     → fallback STT      │
│  Groq LLM           → conversation AI   │
│  gTTS + pygame-ce   → text-to-speech    │
│  eo_to_pl_phonetic  → Eo TTS workaround │
│  MP3 archive        → poems & music     │
└─────────────────────────────────────────┘
```

The hub handles all physical I/O. The PC handles all computation. Each does what it does best — this split is intentional and explainable to judges.

The laptop is **fully compliant** with WRO rules: the category allows any number of controllers of any type. The hub + PC pair satisfies "one or more controllers" and the BLE link demonstrates multi-device software engineering — one of the explicitly scored criteria.

---

## Six Modes

| Mode | What it does | How it decides |
|---|---|---|
| **FLASHCARDS** (0) | Speaks an Esperanto word, user answers YES/NO. Unit filter supported. | SM-2 spaced repetition — interval grows with each correct answer. Session summary on exit. |
| **POEMS** (1) | Plays Esperanto poetry MP3s with metadata | Adaptive queue — weights by play count, recency, rating |
| **MUSIC** (2) | Plays Esperanto music MP3s with metadata | Same adaptive queue algorithm |
| **CONVERSATION** (3) | Live dialogue in Esperanto with AI | LLM adapts vocabulary to level (A1/B1/C1); detects cultural keywords → offers media transition |
| **ATTRACT** (4) | Greets passersby, plays quizzes, music snippets, facts | Randomised sequence engine; activates on motion detection |
| **A0 LESSON** (5) | Scripted lessons (no AI): Greetings, Numbers, Culture, Technology. Fully offline. | Deterministic script; Technology lesson auto-switches flashcards to Technology filter |

None of the decisions in modes 0–4 are pre-scripted. SM-2 calculates which word to show based on your answer history. The adaptive queue weights media by multiple factors. The LLM generates a unique response to every utterance.

---

## Three Layers of Autonomous Decision-Making

This is the core argument for the WRO "autonomous decisions" criterion:

**1. SM-2** decides *which word* to show and *when*, based on individual response history. The easiness factor and interval grow exponentially with correct answers — the robot builds a personalised model of what you know. When you leave the mode, it speaks a summary: *"8 correct, 4 wrong. Weakest word: pomo."*

**2. Adaptive media queue** picks the next poem or music track based on `play_count`, `last_played`, and `rating`. Formula: `weight = (5/play_count + recency_bonus × 0.3) × rating_multiplier`. A track played recently is deprioritised; a highly rated one is upweighted. No two sessions are the same.

**3. LLM in ConversationMode** generates a unique response to every utterance, adapts its vocabulary to the user's level (A1/B1/C1), and detects cultural context — if the reply contains keywords like *muziko*, *poezio*, *kulturo*, it proactively offers to transition to the relevant media mode.

---

## Hardware

| Component | Port | Function |
|---|---|---|
| Hub SPIKE Prime | — | Control centre: LED matrix, speaker, I/O, BLE |
| Ultrasonic sensor | A | Detects human presence up to ~200 cm; last-good-value cache eliminates false `None` |
| Scanning motor | B | Sweeps ±45° + 15° mount offset; debounce eliminates jitter |
| Flag motor | D | Pendulum animation 0°→+10° waves the Esperanto flag |
| ForceSensor LEFT | E | Short = NO / previous; Long (800 ms) = open mode menu |
| ForceSensor RIGHT | F | Short = YES / next / push-to-talk; Long = repeat definition / metadata / change level |
| PC / Steam Deck | BLE ↔ hub | wav2vec2 STT, gTTS, SM-2, adaptive queue, Groq API, pygame-ce |

---

## Real Problem, Real Consultation

> *"It's hard to start, because you don't know where to find materials."*
> — feedback from an Esperanto speaker consulted during project development

Esperanto has no government, no national academy, no institution protecting it. Its speakers are distributed across the world with no central hub for learning resources. This robot addresses that directly: it teaches the language, preserves its culture, and invites conversation — in a single physical device, without internet for core functions.

We consulted with members of the Polish Esperanto community (Polskie Towarzystwo Esperantystów — pte.pl) to validate the problem and inform word list priorities.

---

## Key Innovation & Slogan

**What makes this different from an app?**
Physical buttons, a scanning motor, a glowing LED matrix, and a speaker that greets you when you walk up — the robot is *present* in the room in a way a phone screen is not. It invites interaction instinctively.

**What makes this different from other robots?**
Most educational robots teach *about* a subject. This robot *is* the subject — it speaks Esperanto, archives Esperanto culture, holds a conversation in the language. It is the artifact and the teacher simultaneously.

> **Slogan:** *"One language for all — one robot to teach it."*

---

## File Structure

```
.
├── hub.py                          # SPIKE Prime firmware (MicroPython/Pybricks)
├── computer.py                     # PC logic (Python 3.11+)
├── requirements.txt                # Python dependencies (pip install -r requirements.txt)
├── config.json                     # API keys & runtime config (not committed)
├── tools/
│   └── import_wordlist.py          # Digitisation tool: TSV/CSV → wordlist.json
└── assets/
    ├── flashcards/
    │   └── wordlist.json           # 122 words in 10 thematic units, with SM-2 state
    ├── poems/
    │   ├── poems.json              # Metadata: title, author, year, themes
    │   └── *.mp3                   # Esperanto poetry audio files
    └── music/
        ├── music.json              # Metadata: title, artist, genre, origin
        └── *.mp3                   # Esperanto music audio files
```

### wordlist.json — example entry
```json
{
  "word": "espero",
  "translation": "hope / nadzieja",
  "pronunciation": "es-PE-ro",
  "unit": "Culture",
  "part_of_speech": "noun",
  "sr_ease": 2.5,
  "sr_interval": 3,
  "sr_repetitions": 2,
  "next_review": "2026-05-12T10:00:00",
  "correct_count": 5,
  "wrong_count": 1
}
```

### poems.json / music.json — example entry
```json
{
  "id": "p001",
  "filename": "la_espero.mp3",
  "title": "La Espero",
  "author": "L. L. Zamenhof",
  "year": 1887,
  "origin": "Poland",
  "themes": ["hope", "unity", "language"],
  "description": "The anthem of the Esperanto movement.",
  "play_count": 0,
  "last_played": null,
  "rating": null
}
```

---

## Setup

### Requirements
- Python 3.11+
- LEGO SPIKE Prime with [Pybricks firmware](https://code.pybricks.com)
- Bluetooth LE enabled on PC (BlueZ on Linux / built-in on Steam Deck)

### Install
```bash
# Recommended: virtual environment
python3 -m venv espero_env
source espero_env/bin/activate        # Linux / macOS / Steam Deck
# .\espero_env\Scripts\activate       # Windows

pip install -r requirements.txt
```

> **Note on `torch`:** the first `pip install` downloads ~2 GB (PyTorch + wav2vec2 model). Subsequent runs use the local cache — startup is fast after the first time.

### Config
Create `config.json` in the project root:
```json
{
  "groq_api_key": "YOUR_KEY_HERE",
  "groq_model": "llama-3.3-70b-versatile",
  "whisper_model": "base",
  "whisper_device": "cpu",
  "audio_record_seconds": 6,
  "audio_activity_db": -30
}
```

Alternatively, set `GROQ_API_KEY` as an environment variable (or in a `.env` file — `python-dotenv` is included).

### Run
```bash
python computer.py
```
The script connects to the hub over BLE automatically, retrying up to 3 times on failure.

### Digitise a dictionary (digitisation tool)
```bash
# Import from TSV (word<TAB>translation / pl)
python tools/import_wordlist.py my_dictionary.tsv

# Preview without writing anything
python tools/import_wordlist.py my_dictionary.tsv --dry-run

# Custom wordlist path
python tools/import_wordlist.py source.csv --wordlist assets/flashcards/wordlist.json
```

Legal Esperanto music and poetry sources: [Jamendo](https://jamendo.com), [Vinilkosmo](https://vinilkosmo-mp3.com)

---

## Controls

| Button | Short press | Long press (800 ms) |
|---|---|---|
| **RIGHT** | YES / Correct / Next track / Push-to-talk | Repeat definition / Read metadata / Change difficulty |
| **LEFT** | NO / Wrong / Previous track / Cancel turn | Open mode menu |

**In menu:** RIGHT cycles through modes (0–5), LEFT confirms.

---

## BLE Signal Protocol (hub → PC)

| Signal | Meaning |
|---|---|
| `YES` | FC: correct \| MEDIA: next \| CONV: push-to-talk \| ATTRACT: instructions |
| `NO` | FC: wrong \| MEDIA: previous \| CONV: cancel \| ATTRACT: skip |
| `ACTION_HOLD` | FC: repeat definition \| MEDIA: read metadata \| CONV: change level |
| `MODE:<n>` | Switch to mode n (0–5) |
| `SLEEP` | Hub entering sleep (inactivity timeout) |
| `WAKE` | Hub detected presence → enters ATTRACT |
| `ATTRACT_ENTER` | Hub confirmed attract mode active |
| `ATTRACT_LOST` | Nobody in range for 30 s → go back to sleep |
| `ATTRACT_EXIT` | Button pressed in attract → stop immediately, open menu |
| `FILTER:<unit>` | Set flashcard filter (e.g. `FILTER:Technology`) → switch to FLASHCARDS |
| `LESSON_FILTER:<unit>` | After A0 lesson → switch flashcards to given unit filter |

---

## Roadmap — Implementation Status

| ID | Description | Status |
|---|---|---|
| H1 | Typo fix: `riди` → `ridi` in attract word list | ✅ done |
| H2 | Scan motor debounce — `run_target()` only fires on target change | ✅ done |
| H3 | Distance sensor last-good-value cache — eliminates false `None` | ✅ done |
| H4 | Whisper fallback language `"it"` → `None` (auto-detection) | ✅ done |
| H5 | Session summary spoken on FlashcardsMode exit | ✅ done |
| P2 | Context-aware CONV→MEDIA transition on cultural keywords in LLM reply | ✅ done |
| P4 | `tools/import_wordlist.py` — TSV/CSV digitisation tool with dedup and dry-run | ✅ done |
| P3 | README narrative — SDG 17, slogan, cultural statement | ✅ this file |
| **P6** | Test `lang="eo"` (Esperanto TTS) in gTTS — hook ready in `_speak()` | 🔄 pending |
| **P7** | Populate `poems.json` and `music.json` with 2–3 real entries before competition | 🔄 pending |

---

## For Judges

**"How does the robot make autonomous decisions?"**
Three independent layers: SM-2 calculates flashcard intervals from your individual answer history. The adaptive queue weighs media by play count, recency, and rating. The LLM generates a unique reply to every spoken sentence and detects whether the conversation touches on Esperanto culture — offering to play relevant media without any prompt from the user.

**"Why Esperanto?"**
An Esperanto speaker we consulted told us directly: quality materials are hard to find. Esperanto has no country and no institution to protect it. This robot is a concrete response to that gap.

**"Why a laptop and not a Raspberry Pi?"**
SPIKE Prime handles all physical I/O — sensors, motors, LED, buttons. The laptop handles compute-heavy tasks: a ~1 GB speech recognition model (wav2vec2), real-time TTS synthesis, and LLM API calls. Splitting by capability is a deliberate engineering choice. A Raspberry Pi could do the same job but would make development slower and demos less reliable — there is no technical or regulatory reason to change.

**"Does it work offline?"**
Flashcards, poems, music, A0 lessons — fully offline. Conversation requires internet (Groq API). Speech recognition (wav2vec2) runs locally on the laptop.

**"What AI systems were used?"**

| System | Purpose | Scope |
|---|---|---|
| Groq / LLaMA 3.3 70B | ConversationMode responses | Cloud API; requires internet |
| wav2vec2-large-xlsr-53-eo | Esperanto speech recognition (primary STT) | Local, offline, CC-BY 4.0 |
| faster-whisper | Fallback STT (auto language detection) | Local, offline, MIT |
| SM-2 algorithm | Flashcard scheduling | Local, public domain |
| Claude (Anthropic) | Code debugging during development | Not in the robot itself |
| ChatGPT (OpenAI) | Subject matter support during development | Not in the robot itself |

**"What would you improve with more time?"**
Esperanto TTS (`lang="eo"`) — the code path is ready, we need to test audio quality on the actual device. A larger curated word list imported from open Esperanto dictionaries (ReVo, ESPDIC) using the digitisation tool we built. A local LLM (llama.cpp) so ConversationMode works offline too.

---

## Credits

- Esperanto created by L. L. Zamenhof (1887) — public domain
- SM-2 spaced repetition algorithm by Piotr Woźniak — public domain specification
- wav2vec2 Esperanto STT model: [cpierse/wav2vec2-large-xlsr-53-esperanto](https://huggingface.co/cpierse/wav2vec2-large-xlsr-53-esperanto) (CC-BY 4.0)
- Phonetic transcription rules: [martinrue/vocx](https://github.com/martinrue/vocx) (MIT)
- Legal music sources: Jamendo (CC licensed), Vinilkosmo
- WRO 2026 Future Innovators — "Robots Meet Culture"
