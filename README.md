# 🤖 Esperanto Flashcard Robot — WRO 2026 Future Innovators

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
│  Ultrasonic sensor  → detect presence   │
│  Scanning motor     → sweep ±45°        │
│  5×5 LED matrix     → mode display      │
│  Speaker            → beeps & tones     │
│  LEFT / RIGHT buttons → user input      │
└──────────────┬──────────────────────────┘
               │  Bluetooth BLE (pybricksdev)
               │  hub prints signals → PC reads
               ▼
┌─────────────────────────────────────────┐
│              PC (computer.py)           │
│                                         │
│  SM-2 algorithm     → flashcard order   │
│  Adaptive queue     → media selection   │
│  wav2vec2 (local)   → Esperanto STT     │
│  faster-whisper     → fallback STT      │
│  Groq LLM           → conversation AI   │
│  gTTS + pygame      → text-to-speech    │
│  MP3 archive        → poems & music     │
└─────────────────────────────────────────┘
```

The hub handles all physical I/O. The PC handles all computation. Each does what it does best — this split is intentional and explainable to judges.

The laptop is **fully compliant** with WRO rules: the category allows any number of controllers of any type. The hub + PC pair satisfies "one or more controllers" and the BLE link demonstrates multi-device software engineering — one of the explicitly scored criteria.

---

## Five Modes

| Mode | What it does | How it decides |
|---|---|---|
| **FLASHCARDS** | Speaks an Esperanto word, user answers YES/NO | SM-2 spaced repetition — interval grows with each correct answer |
| **POEMS** | Plays Esperanto poetry MP3s with metadata | Adaptive queue — weights by play count, recency, rating |
| **MUSIC** | Plays Esperanto music MP3s with metadata | Same adaptive queue algorithm |
| **CONVERSATION** | Live dialogue in Esperanto with AI | LLM adapts vocabulary to level (A1/B1/C1); detects cultural keywords and offers media transition |
| **ATTRACT** | Greets passersby, plays quizzes, music snippets, facts | Randomized sequence engine; activates on motion detection |

None of these decisions are pre-scripted. SM-2 calculates which word to show based on your answer history. The adaptive queue weights media by multiple factors. The LLM generates a unique response to every utterance.

---

## Three Layers of Autonomous Decision-Making

This is the core argument for the WRO "autonomous decisions" criterion:

**1. SM-2** decides *which word* to show and *when*, based on individual response history. The interval between reviews grows exponentially with correct answers — the robot builds a personalized model of what you know. When you leave the mode, it speaks a summary: *"8 correct, 4 wrong. Weakest word: pomo."*

**2. Adaptive media queue** picks the next poem or music track based on `play_count`, `last_played`, and `rating`. A track played recently is deprioritized; a highly rated one is upweighted. No two sessions are the same.

**3. LLM in ConversationMode** generates a unique response to every utterance, adapts its vocabulary to the user's level (A1/B1/C1), and detects cultural context — if the reply contains keywords like *muziko*, *poezio*, *kulturo*, it proactively offers to transition to the relevant media mode.

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
├── config.json                     # API keys & runtime config (not committed)
├── tools/
│   └── import_wordlist.py          # Digitization tool: TSV/CSV → wordlist.json
└── assets/
    ├── flashcards/
    │   └── wordlist.json           # Esperanto word list with SM-2 state per word
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
  "sr_ease": 2.5,
  "sr_interval": 3,
  "sr_repetitions": 2,
  "next_review": "2026-03-24T10:00:00",
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
- Bluetooth enabled on PC

### Install
```bash
pip install pybricksdev gtts pygame sounddevice numpy faster-whisper groq transformers torch
```

### Config
Create `config.json` in the project root:
```json
{
  "groq_api_key": "YOUR_KEY_HERE",
  "groq_model": "llama-3.3-70b-versatile",
  "whisper_model": "base",
  "whisper_device": "cpu",
  "audio_record_seconds": 6
}
```

### Run
```bash
python computer.py
```
The script connects to the hub over BLE automatically, retrying up to 3 times on failure.

### Digitize a dictionary (Pont 4 — digitalization tool)
```bash
# Import from TSV (word<TAB>translation en / pl)
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

**In menu:** RIGHT cycles through modes, LEFT confirms.

---

## Roadmap — Implementation Status

All items from ROADMAP.md are now implemented:

| ID | Description | Status |
|---|---|---|
| H1 | Typo fix: `riди` → `ridi` in attract word list | ✅ done |
| H2 | Scan motor debounce — `run_target()` only fires on target change, eliminates jitter | ✅ done |
| H3 | Distance sensor last-good-value cache — eliminates false "nobody there" on transient None | ✅ done |
| H4 | Whisper fallback language `"it"` → `None` (auto-detection) | ✅ done |
| H5 | Session summary spoken on FlashcardsMode exit: correct / wrong / weakest word | ✅ done |
| P2 | Context-aware CONV→MEDIA transition on cultural keywords in LLM reply | ✅ done |
| P4 | `tools/import_wordlist.py` — TSV/CSV digitization tool with dedup and dry-run | ✅ done |
| P3 | README narrative — SDG 17, slogan, cultural statement | ✅ this file |

Remaining lower-priority items:
- **P6** — Test `lang="eo"` (Esperanto TTS) in gTTS; switch if audio quality is acceptable. Hook already in `_speak()`.
- **P7** — Populate `poems.json` and `music.json` with 2–3 real entries before competition day.

---

## For Judges

**"How does the robot make autonomous decisions?"**
Three independent layers: SM-2 calculates flashcard intervals from your individual answer history. The adaptive queue weighs media by play count, recency, and rating. The LLM generates a unique reply to every spoken sentence and now also detects whether the conversation touches on Esperanto culture — offering to play relevant media without any prompt from the user.

**"Why Esperanto?"**
An Esperanto speaker we consulted told us directly: quality materials are hard to find. Esperanto has no country and no institution to protect it. This robot is a concrete response to that gap.

**"Why a laptop and not a Raspberry Pi?"**
SPIKE Prime handles all physical I/O — sensors, motor, LED, buttons. The laptop handles compute-heavy tasks: a 1GB speech recognition model (wav2vec2), real-time TTS synthesis, and LLM API calls. Splitting by capability is a deliberate engineering choice. A Raspberry Pi could do the same job but would make development slower and demos less reliable — there is no technical or regulatory reason to change.

**"Does it work offline?"**
Flashcards, poems, music — fully offline. Conversation requires internet (Groq API). Speech recognition (wav2vec2) runs locally on the laptop.

**"What would you improve with more time?"**
Esperanto TTS (`lang="eo"`) — the code path is ready, we need to test audio quality on the actual device. A larger curated word list imported from open Esperanto dictionaries using the digitization tool we built.

---

## Credits

- Esperanto created by L. L. Zamenhof (1887) — public domain
- SM-2 spaced repetition algorithm by Piotr Woźniak — public domain specification
- wav2vec2 Esperanto STT model: [cpierse/wav2vec2-large-xlsr-53-esperanto](https://huggingface.co/cpierse/wav2vec2-large-xlsr-53-esperanto)
- Legal music sources: Jamendo (CC licensed), Vinilkosmo
- WRO 2026 Future Innovators — "Robots Meet Culture"