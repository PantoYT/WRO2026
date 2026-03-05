# 🤖 Esperanto Robot – WRO 2026 Future Innovators
## "Robots Meet Culture" – An Educational Language Learning Robot

A LEGO Mindstorms 51515 robot that teaches Esperanto language and Esperanto culture, built for the WRO 2026 Future Innovators competition (theme: "Robots Meet Culture").

**Features:**
- ✨ Friendly AI robot with expressive animated eyes
- 🎓 8 interactive learning modes (flashcards, poetry, songs, facts, history, pronunciation, AI chatbot)
- 🎤 Speech recognition for pronunciation practice
- 🎵 Music and text-to-speech playback
- 📱 Tablet/laptop brain with hub physical interface  
- 🌐 Works in **two modes**: **Hubbed** (with LEGO robot) and **Hubless** (keyboard demo mode)
- 🔒 AI safety features with prompt injection protection
- 📚 Modular design – easily add new learning modes

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [System Architecture](#system-architecture)
3. [Running the Robot](#running-the-robot)
4. [Hubbed Mode (with LEGO Robot)](#hubbed-mode-with-lego-robot)
5. [Hubless Mode (Keyboard Demo)](#hubless-mode-keyboard-demo)
6. [Communication Protocol](#communication-protocol)
7. [Learning Modes Guide](#learning-modes-guide)
8. [Installation & Setup](#installation--setup)
9. [Adding Content](#adding-content)
10. [Troubleshooting](#troubleshooting)
11. [WRO Competition Alignment](#wro-competition-alignment)

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LAPTOP                                       │
│                                                                     │
│  main.py ──────────────────────────────────────────────────────────►│
│    │                                                                │
│    ├── SerialInterface    ◄──────── USB JSON ──────────────────────►│
│    │       │                                                        │
│    ├── ModeManager        (state machine, dispatches button events) │
│    │       │                                                        │
│    │       ├── FlashcardModule    (vocabulary CSV files)            │
│    │       ├── PoemModule         (poem TXT files)                  │
│    │       ├── SongModule         (MP3/WAV files)                   │
│    │       ├── FactModule         (facts TXT file)                  │
│    │       ├── ZamenhofModule     (zamenhof facts TXT file)         │
│    │       ├── PronunciationModule (microphone + STT)               │
│    │       └── AIAssistantModule  (HTTP → Groq/OpenRouter/Ollama)   │
│    │                                                                │
│    ├── AudioPlayer        (pyttsx3 TTS + pygame file playback)      │
│    ├── EyeAnimator        (Tkinter window – robot face)             │
│    └── FaceTracker        (OpenCV webcam – face detection)          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                    │  USB serial cable  │
┌─────────────────────────────────────────────────────────────────────┐
│                    LEGO MINDSTORMS 51515 HUB                        │
│                                                                     │
│  hub_main.py (Pybricks MicroPython)                                 │
│    - Reads buttons A (left) and B (right)                           │
│    - Sends JSON events to laptop                                    │
│    - Receives JSON commands to show icons on 5×5 LED display        │
│    - Auto-sleeps after 1 minute of inactivity                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Design principles

- **The hub is only a physical interface.** It has no intelligence – it just reports button presses and shows icons.
- **The laptop does all thinking.** Language processing, AI, audio, vision, state management.
- **Modular.** Each learning mode is a self-contained class. Adding a new mode = adding one file + registering it in `mode_manager.py`.
- **Safe for public interaction.** The AI assistant is strictly restricted to Esperanto topics with prompt injection protection.

---

## 2. Communication Protocol

All messages are single-line JSON objects terminated with `\n`, sent over USB serial (default: 115200 baud).

### Hub → Laptop

| Message | When sent |
|---------|-----------|
| `{"type": "HUB_READY", "version": "1.0"}` | On startup |
| `{"type": "BUTTON_A_PRESS", "hold": false}` | Short press of left button |
| `{"type": "BUTTON_A_PRESS", "hold": true}` | Hold left button (>800 ms) |
| `{"type": "BUTTON_B_PRESS", "hold": false}` | Short press of right button |
| `{"type": "BUTTON_B_PRESS", "hold": true}` | Hold right button (>800 ms) |
| `{"type": "WAKE_EVENT", "source": "button"}` | Button pressed while sleeping |
| `{"type": "IDLE_TIMEOUT"}` | Auto-sleep after 1 min inactivity |

### Laptop → Hub

| Message | Effect |
|---------|--------|
| `{"type": "SHOW_ICON", "icon": "HAPPY"}` | Show named icon on 5×5 display |
| `{"type": "SHOW_TEXT", "text": "Hi"}` | Scroll text across display |
| `{"type": "ENTER_SLEEP"}` | Turn off display, flag as sleeping |
| `{"type": "WAKE_UP"}` | Resume normal display |
| `{"type": "SET_COLOR", "color": "BLUE"}` | Set hub status LED color |

### Button actions (UX contract)

| Button | Short press | Hold |
|--------|-------------|------|
| A (left) | Next item / reveal | Go back to menu |
| B (right) | Confirm / play | Repeat last audio |

---

## 3. Folder Structure

```
robot_project/
│
├── hub_code/
│   └── hub_main.py              ← Pybricks MicroPython (runs ON the hub)
│
├── laptop/
│   ├── main.py                  ← Entry point
│   ├── serial_interface.py      ← USB serial communication
│   ├── mode_manager.py          ← Central state machine
│   │
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── audio_player.py      ← TTS + audio file playback
│   │   ├── flashcards.py        ← Vocabulary flashcard mode
│   │   ├── poems.py             ← Poetry recitation mode
│   │   ├── songs.py             ← Song playback mode
│   │   ├── facts.py             ← Language facts mode
│   │   ├── zamenhof.py          ← Zamenhof history mode
│   │   ├── pronunciation.py     ← Pronunciation training mode
│   │   └── ai_assistant.py      ← AI chatbot (Esperanto-only)
│   │
│   └── vision/
│       ├── __init__.py
│       ├── eye_animation.py     ← Robot face / eyes (Tkinter)
│       └── face_tracking.py     ← Webcam face detection (OpenCV)
│
├── data/
│   ├── vocabulary/
│   │   └── basic.csv            ← Esperanto word pairs (add more CSVs here)
│   ├── poems/
│   │   └── La_Espero.txt        ← Esperanto poems (one poem per .txt file)
│   ├── songs/                   ← Put .mp3 / .wav songs here
│   └── facts/
│       ├── language_facts.txt   ← One fact per line
│       └── zamenhof_facts.txt   ← One fact per line
│
├── requirements.txt
├── ai_config.template.json      ← Copy to ai_config.json and add your key
└── README.md
```

---

## 4. Required Libraries

### Hub (Pybricks MicroPython – installed via Pybricks firmware)
- `pybricks` – built into the firmware, no extra install needed

### Laptop (Python 3.10+)

| Library | Purpose | Required? |
|---------|---------|-----------|
| `pyserial` | USB serial communication with hub | **Yes** |
| `pygame` | Audio file playback (MP3/WAV) | **Yes** |
| `pyttsx3` | Offline text-to-speech | Recommended |
| `gTTS` | Online TTS with Esperanto support | Optional |
| `SpeechRecognition` | Microphone input for pronunciation mode | Optional |
| `pyaudio` | Microphone hardware access | Optional |
| `opencv-python` | Webcam face tracking | Optional |
| `requests` | HTTP calls to AI API | Optional (AI mode) |

---

## 5. Installation & Setup

### Step 1 – Install Python dependencies

```bash
pip install -r requirements.txt
```

For microphone support (Linux):
```bash
sudo apt install portaudio19-dev python3-pyaudio
```

### Step 2 – Flash Pybricks firmware onto the hub

1. Go to https://pybricks.com/install/
2. Follow instructions for LEGO SPIKE Prime / Mindstorms 51515
3. Use the Pybricks IDE to upload `hub_code/hub_main.py`

### Step 3 – Configure AI assistant (optional)

```bash
cp ai_config.template.json ai_config.json
# Edit ai_config.json and add your API key
```

Free AI options:
- **Groq** (recommended): https://console.groq.com – free, very fast
- **OpenRouter**: https://openrouter.ai – many free models
- **Ollama**: https://ollama.ai – fully offline, no API key needed
  ```bash
  # Install Ollama, then:
  ollama pull llama3
  # Set provider to "ollama" in ai_config.json
  ```

### Step 4 – Add content

- Vocabulary: add `.csv` files to `data/vocabulary/` (format: `esperanto,translation,notes`)
- Poems: add `.txt` files to `data/poems/` (filename becomes the title)
- Songs: add `.mp3` or `.wav` files to `data/songs/`
- Facts: add lines to `data/facts/language_facts.txt`

---

## 6. Running the System

### With a physical hub connected:
```bash
cd laptop
python main.py
# The system auto-detects the serial port.
# If it fails, specify it manually:
python main.py --port /dev/ttyACM0        # Linux
python main.py --port COM3                # Windows
python main.py --port /dev/cu.usbmodem1  # macOS
```

### Without a hub (demo / development mode):
```bash
cd laptop
python main.py --no-hub
# Type keyboard commands: a=ButtonA  b=ButtonB  A=HoldA  B=HoldB  q=Quit
```

### Logs
All events are logged to `robot.log` and also printed to the terminal.

---

## 7. Adding Content

### Adding a new vocabulary set
Create `data/vocabulary/intermediate.csv`:
```csv
esperanto,translation,notes
ĉevalo,horse,animal
birdo,bird,animal
arbo,tree,nature
```
The flashcard module automatically picks up all `.csv` files in the folder.

### Adding a poem
Create `data/poems/Mia_Penso.txt` and paste the poem text.
The poem title displayed to users will be `Mia Penso`.

### Adding a new mode (for developers)
1. Create `laptop/modules/my_mode.py` with a class that has `start()`, `stop()`, `on_button_a()`, `on_button_b()` methods.
2. Add the mode to the `Mode` enum in `mode_manager.py`.
3. Add it to the `MENU_ITEMS` list.
4. Wire it in `main.py` and assign it to `manager.my_mode`.

---

## 8. Free Data Sources

### Esperanto vocabulary
- **Komputaĵoj / lernu!**: https://lernu.net/en/vortaro – free dictionary
- **Wiktionary Esperanto**: https://eo.wiktionary.org
- **Kurso de Esperanto (CSV-format wordlists)**: search GitHub for "esperanto wordlist"
- **ESPDIC**: http://www.denisowski.org/Esperanto/ESPDIC/ – 16,000-word English–Esperanto dictionary (public domain)

### Esperanto poems
- **Vikifontaro** (Esperanto Wikisource): https://eo.wikisource.org – public domain poems
- **Originalaj Verkoj de Zamenhof**: https://eo.wikisource.org/wiki/Zamenhof
- **Esperanto literature collection**: https://www.gutenberg.org (search "Esperanto")

### Esperanto songs
- **Vinilkosmo records** (some free downloads): https://www.vinilkosmo-mp3.com
- **YouTube** (for personal/demo use): search "Esperanto kanto"
- **La Espero** (official anthem) – public domain, sheet music and recordings widely available

### Esperanto cultural facts
- **Wikipedia Esperanto article**: https://en.wikipedia.org/wiki/Esperanto
- **Esperanto-USA**: https://www.esperanto-usa.org
- **Universala Esperanto-Asocio**: https://uea.org

---

## 9. WRO Competition Alignment

This project addresses all three areas of the WRO 2026 "Robots Meet Culture" theme:

**Area 1 – Protecting cultural heritage**
The robot preserves the Esperanto language and its culture by teaching it interactively,
making it accessible to anyone regardless of language background.

**Area 2 – Co-creation: humans, robots and AI**
The AI assistant mode creates a collaborative learning experience where human curiosity
and AI knowledge work together, restricted to Esperanto culture for safety and focus.

**Area 3 – Experiencing art and history with robots**
Poetry, song, and Zamenhof history modes bring Esperanto's rich cultural history to life
through audio, animation, and interactive storytelling.

**UN Sustainable Development Goals addressed:**
- SDG 4: Quality Education (accessible language learning)
- SDG 10: Reduced Inequalities (Esperanto as a neutral, equal-access language)
- SDG 11: Sustainable Cities and Communities (cultural heritage preservation)
- SDG 17: Partnerships for the Goals (global Esperanto community)
