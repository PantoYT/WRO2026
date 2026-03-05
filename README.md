# 🤖 Esperanto Robot – WRO 2026 Future Innovators
## "Robots Meet Culture" – An Educational Language Learning Robot

A LEGO Mindstorms 51515 robot that teaches Esperanto language and Esperanto culture, built for the WRO 2026 Future Innovators competition (theme: "Robots Meet Culture").

**Features:**
- ✨ Friendly AI robot with expressive animated eyes (warm colors, pupils, smiles!)
- 🎓 8 interactive learning modes (flashcards, poetry, songs, facts, history, pronunciation, AI chatbot)
- 🎤 Speech recognition for pronunciation practice
- 🎵 Music and text-to-speech playback
- 📱 Tablet/laptop brain with hub physical interface  
- 🌐 Works in **two modes**: **Hubbed** (with LEGO robot) and **Hubless** (keyboard demo mode)
- 🔒 AI safety features with prompt injection protection
- 📚 Modular design – easily add new learning modes

---

## Quick Start (5 Minutes)

### For testing without LEGO hardware:
```bash
pip install -r requirements.txt
cd laptop
python main.py --no-hub

# Keyboard controls:
# a = Next,  b = Confirm,  A = Back,  B = Repeat,  q = Quit
```

### With LEGO Mindstorms 51515 Hub:
```bash
# 1. Upload hub_code/hub_main.py to hub using Pybricks IDE (pybricks.com)
# 2. Connect hub via USB
# 3. Run:
cd laptop
python main.py
```

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Running the Robot](#running-the-robot)
3. [Hubbed Mode (with LEGO Robot)](#hubbed-mode-with-lego-robot)
4. [Hubless Mode (Keyboard Demo)](#hubless-mode-keyboard-demo)
5. [Learning Modes Guide](#learning-modes-guide)
6. [Installation & Setup](#installation--setup)
7. [Communication Protocol](#communication-protocol)
8. [Adding Content](#adding-content)
9. [Troubleshooting](#troubleshooting)
10. [WRO Competition Alignment](#wro-competition-alignment)

---

## System Architecture

```
┌──────────────────────────────────── LAPTOP / TABLET ──────────────────────────────────────┐
│                                                                                           │
│  main.py (Python entry point)                                                            │
│    ├── SerialInterface      (USB ↔ Hub communication via JSON)                            │
│    ├── ModeManager          (State machine & button dispatch)                            │
│    │                                                                                     │
│    ├── 📚 Learning Modules:                                                              │
│    │   ├── FlashcardModule     (vocabulary flashcards)                                  │
│    │   ├── PoemModule          (poetry recitation)                                      │
│    │   ├── SongModule          (music playback)                                         │
│    │   ├── FactModule          (language facts & trivia)                                │
│    │   ├── ZamenhofModule      (history of Esperanto creator)                          │
│    │   ├── PronunciationModule (microphone-based training)                              │
│    │   └── AIAssistantModule   (Esperanto chatbot - safe & restricted)                  │
│    │                                                                                     │
│    ├── AudioPlayer          (pyttsx3 TTS + pygame playback)                              │
│    ├── EyeAnimator          (Tkinter GUI – friendly, expressive face)                    │
│    └── FaceTracker          (OpenCV – tracks viewer's gaze for eye contact)              │
│                                                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                                    ↕ USB Serial
┌───────────────────────────────── LEGO MINDSTORMS 51515 HUB ────────────────────────────────┐
│                                                                                           │
│  hub_main.py (Pybricks MicroPython)                                                      │
│    ├── Button A & B detection + hold timing                                              │
│    ├── 5×5 LED display (shows icons, text)                                               │
│    ├── Status light color control                                                        │
│    └── Auto-sleep after 1 minute inactivity                                              │
│                                                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

**Design Philosophy:**
- **Hub is ONLY a physical interface** – buttons, LED display, lights (no AI/logic)
- **Laptop does ALL thinking** – language, AI, audio, vision, state management
- **Modular architecture** – each mode is a self-contained Python class
- **Simple communication** – JSON over USB serial
- **Public-safe** – AI restricted to Esperanto topics with injection protection

---

## Running the Robot

### Hubbed Mode (with LEGO Robot)

Use this when you have a **LEGO Mindstorms 51515 hub** connected via USB.

**Prerequisites:**
- LEGO Mindstorms 51515 hub
- Pybricks firmware ([pybricks.com](https://pybricks.com/install/))
- USB cable
- Python 3.9+ on laptop

**Setup:**

1. **Upload hub code to robot:**
   - Connect hub to laptop via USB
   - Open [Pybricks IDE](https://ide.pybricks.com)
   - Open `hub_code/hub_main.py`
   - Click **Send to Hub**
   - Hub LED should turn blue (indicates running code)

2. **Run laptop side:**
   ```bash
   cd laptop
   python main.py
   ```
   
   The system will:
   - Auto-detect the hub COM port
   - Open friendly robot face window
   - Announce "Bonvenon!" (Welcome!)
   - Display menu on hub's 5×5 LED

**Button Layout:**

| Button | Short Press | Long Hold |
|--------|-------------|-----------|
| **A (left)** | Next item / Reveal answer / Exit mode | Go back to menu |
| **B (right)** | Confirm choice / Play audio | Repeat last audio |

**What Each Learning Mode Does:**

| Mode | Button A | Button B | Purpose |
|------|----------|----------|---------|
| Menu | Next mode | Select mode | Choose from 8 learning activities |
| Flashcards | Show answer / Next | Hear word | Practice vocabulary |
| Poetry | Next poem | Read aloud | Recite Esperanto poems |
| Songs | Next song | Play song | Listen to Esperanto music |
| Facts | Next fact | Repeat fact | Learn language trivia |
| Zamenhof | Next fact | Repeat fact | Learn about Zamenhof (creator) |
| Pronunciation | Next word | Record & check | Practice speaking via microphone |
| AI Chat | Clear history | Ask question | Talk with Esperanto chatbot |

---

### Hubless Mode (Keyboard Demo)

Use this for **development, testing, or when you don't have a hub**. Everything works identically, but you control via keyboard.

**Prerequisites:**
- Python 3.9+
- No hardware!

**Run:**
```bash
cd laptop
python main.py --no-hub
```

**Keyboard Controls:**
```
a  = Short press button A  (navigate, reveal, confirm)
b  = Short press button B  (confirm, play, record)
A  = Long hold button A    (go back to menu)
B  = Long hold button B    (repeat last audio)
q  = Quit the program
```

The robot face appears in a window. Type in the terminal to control it:

```
[Demo] a=Next  b=Confirm  A=Back  B=Repeat  q=Quit > a
[Demo] a=Next  b=Confirm  A=Back  B=Repeat  q=Quit > b
... audio plays ...
[Demo] a=Next  b=Confirm  A=Back  B=Repeat  q=Quit > A
[Back to menu]
```

**Why Use Hubless Mode?**
- ✅ Quick testing without hardware
- ✅ Develop new modes/features
- ✅ Debug issues easily
- ✅ Share robot experience when hub unavailable
- ✅ Works on any computer with Python

---

## Learning Modes Guide

### 1. 📇 Flashcards (Flaŝkartoj)
**Learn vocabulary** by drilling word pairs with spaced repetition.

- **Data:** `data/vocabulary/*.csv`
- **Format:** `esperanto,translation,notes` (one per line)
- **Button A:** Reveal translation → Advance to next card
- **Button B:** Hear Esperanto word pronounced (TTS)
- **Feature:** Shuffles on each session for variety

**Example CSV (`basic.csv`):**
```csv
esperanto,translation,notes
hundo,dog,common noun
kato,cat,common noun
domo,house,place noun
```

### 2. 📖 Poetry (Poemoj)
**Recite classic Esperanto poems.**

- **Data:** `data/poems/*.txt` (one file per poem)
- **Format:** Plain text UTF-8
- **Button A:** Next poem
- **Button B:** Recite poem aloud (TTS)
- **Filename** becomes the poem title

### 3. 🎵 Songs (Kantoj)
**Listen to Esperanto music.**

- **Data:** `data/songs/*.mp3` or `*.wav`
- **Button A:** Next song
- **Button B:** Play current song
- **Format:** MP3 or WAV audio files

### 4. 💡 Facts (Faktoj)
**Learn interesting facts about the Esperanto language.**

- **Data:** `data/facts/language_facts.txt`
- **Format:** One fact per line
- **Button A:** Next fact
- **Button B:** Repeat current fact
- **Feature:** Shuffles randomly, no two sessions are the same

### 5. 👨‍🔬 Zamenhof History
**Learn about L.L. Zamenhof**, creator of Esperanto.

- **Data:** `data/facts/zamenhof_facts.txt`
- **Button A:** Next fact
- **Button B:** Repeat current fact
- **Fallback:** Built-in facts if file is missing

### 6. 🎤 Pronunciation Training (Prononco)
**Practice pronouncing Esperanto words using your microphone.**

- **Data:** Vocabulary from `data/vocabulary/*.csv`
- **How it works:**
  1. Robot says a word via TTS
  2. You press B to start recording
  3. Speak the word into your microphone
  4. Speech recognition compares your pronunciation
  5. Robot gives feedback
- **Button A:** Next word
- **Button B:** Record and check pronunciation

**Requirements:** Install `pyaudio` and `SpeechRecognition`

### 7. 🤖 AI Assistant (AI Asistanto)
**Chat with an AI chatbot about Esperanto!**

- **Features:**
  - ✅ Restricted to Esperanto topics only (SAFE!)
  - ✅ Prompt injection protection built-in
  - ✅ Maintains conversation history for context
  - ✅ Multiple provider support
- **Button A:** Clear conversation history & start fresh
- **Button B:** Type a question (terminal input for now)

**Supported AI Providers:**
- **Groq** (fast, free) – Recommended
- **OpenRouter** (many models)
- **Ollama** (self-hosted, private)

**Setup:**
1. Copy: `ai_config.template.json` → `ai_config.json`
2. Choose your AI provider (see instructions in file)
3. Add API key if using online service
4. Restart robot

---

## Installation & Setup

### 1. Clone/Download the Project
```bash
git clone https://github.com/your-repo/WRO2026.git
cd WRO2026
```

### 2. Install Python 3.9+
- **Windows:** Download from [python.org](https://www.python.org)
- **macOS:** `brew install python3`
- **Linux:** `sudo apt install python3 python3-pip`

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

**What's installed:**
- `pyserial` – USB communication with hub
- `pygame` – Audio playback
- `pyttsx3` – Offline text-to-speech
- `requests` – AI API calls
- `opencv-python` – Webcam (optional)
- `SpeechRecognition` – Microphone (optional)
- `pyaudio` – Microphone input (optional)

**Optional packages:** If installation fails, these are optional and the system degrades gracefully:
- `opencv-python` – Disable with `--camera -1`
- `pyaudio` – Pronunciation mode unavailable
- `SpeechRecognition` – Fallback to phonetic matching

### 4. Organize Data Files
Create this directory structure:
```
WRO2026/
  ├── data/
  │   ├── vocabulary/
  │   │   └── basic.csv           ← Word pairs
  │   ├── poems/
  │   │   ├── La_Espero.txt       ← Provided
  │   │   └── ...                 ← Add your poems
  │   ├── songs/
  │   │   └── *.mp3 or *.wav      ← Add your songs
  │   └── facts/
  │       ├── language_facts.txt
  │       └── zamenhof_facts.txt
  ├── laptop/
  ├── hub_code/
  └── requirements.txt
```

### 5. (Optional) Configure AI Assistant
```bash
cd WRO2026
cp ai_config.template.json ai_config.json
# Edit ai_config.json and add your API key for Groq/OpenRouter/Ollama
```

### 6. (Optional) Upload Hub Code
1. Get **Pybricks IDE** from [pybricks.com](https://pybricks.com/install/)
2. Connect LEGO hub via USB
3. Open `hub_code/hub_main.py` in Pybricks IDE
4. Click **Send to Hub**
5. Hub LED should turn blue

### 7. Run It!

**With hub:**
```bash
cd laptop
python main.py
```

**Without hub (demo mode):**
```bash
cd laptop
python main.py --no-hub
```

**With extra options:**
```bash
# Specify COM port manually (Windows)
python main.py --port COM3

# Disable face tracking
python main.py --camera -1

# Hubless mode
python main.py --no-hub
```

---

## Communication Protocol

All messages between laptop and hub use **JSON over USB serial**, newline-delimited (115200 baud).

### Hub → Laptop (Input from Physical Robot)

| Message | Trigger | Example |
|---------|---------|---------|
| HUB_READY | Startup | `{"type": "HUB_READY", "version": "1.0"}` |
| BUTTON_A_PRESS | Button A released | `{"type": "BUTTON_A_PRESS", "hold": false}` |
| BUTTON_A_PRESS | Button A held >800ms | `{"type": "BUTTON_A_PRESS", "hold": true}` |
| BUTTON_B_PRESS | Button B released | `{"type": "BUTTON_B_PRESS", "hold": false}` |
| BUTTON_B_PRESS | Button B held >800ms | `{"type": "BUTTON_B_PRESS", "hold": true}` |
| WAKE_EVENT | Button press during sleep | `{"type": "WAKE_EVENT", "source": "button"}` |
| IDLE_TIMEOUT | 1+ minute of inactivity | `{"type": "IDLE_TIMEOUT"}` |

### Laptop → Hub (Output to Physical Robot)

| Message | Effect |
|---------|--------|
| `{"type": "SHOW_ICON", "icon": "HAPPY"}` | Display emoji on 5×5 LED |
| `{"type": "SHOW_TEXT", "text": "Hi"}` | Scroll text across LED |
| `{"type": "ENTER_SLEEP"}` | Dim display and hibernate |
| `{"type": "WAKE_UP"}` | Restore normal display |
| `{"type": "SET_COLOR", "color": "BLUE"}` | Set hub status light |

**Available Icons:** HAPPY, SAD, HEART, SMILE, STALLED, ARROW_UP, ARROW_DOWN, ARROW_LEFT, ARROW_RIGHT, CIRCLE, SQUARE

**Available Colors:** WHITE, BLUE, GREEN, RED, YELLOW, ORANGE

---

## Adding Content

### Add Vocabulary
1. Create/edit: `data/vocabulary/my_words.csv`
2. Format: `esperanto,english,notes` (one per line)
3. Create as many .csv files as you want
4. Robot auto-loads all of them
5. Restart → appears in Flashcards mode

### Add Poems
1. Create: `data/poems/My_Amazing_Poem.txt`
2. Paste poem text (UTF-8 encoding)
3. Filename becomes the title
4. Restart → appears in Poetry mode

### Add Songs
1. Drop `song.mp3` or `song.wav` into `data/songs/`
2. Restart → appears in Songs mode

### Add Facts
1. Edit `data/facts/language_facts.txt`
2. One fact per line
3. Use `#` for comments
4. Restart → appears in Facts mode

### Create a Custom Learning Mode
Advanced users can add new modes. Example structure:

**File: `laptop/modules/my_custom_mode.py`**
```python
class MyCustomMode:
    def __init__(self, serial, audio, eyes):
        self.serial = serial
        self.audio = audio
        self.eyes = eyes
    
    def start(self):
        """Called when entering this mode"""
        self.audio.speak("Welcome to my mode!")
    
    def stop(self):
        """Called when leaving this mode"""
        pass
    
    def on_button_a(self):
        """Handle button A press"""
        self.audio.speak("Button A pressed!")
    
    def on_button_b(self):
        """Handle button B press"""
        self.audio.speak("Button B pressed!")
```

Then register in `mode_manager.py`:
1. Add to `MENU_ITEMS` list
2. Add to `Mode` enum
3. Wire in `build_system()` function

---

## Troubleshooting

### Hub Connection Issues
**"No serial port available" / Can't connect to hub**

**Solutions:**
1. Check USB cable is firmly connected
2. On Windows: Find COM port in Device Manager
3. Try manual port: `python main.py --port COM3`
4. Restart hub (disconnect/reconnect USB)
5. Flash Pybricks firmware again

### No Audio Output
**Robot doesn't speak**

**Solutions:**
1. Check system volume control
2. Verify speakers are connected & working
3. Test with: `python main.py --camera -1` (free up resources)
4. Check `robot.log` for error messages

### Microphone Not Working
**Pronunciation mode fails to record**

**Solutions:**
1. Install pyaudio: `pip install pyaudio`
2. macOS: `brew install portaudio && pip install --no-cache-dir pyaudio`
3. Check microphone in system settings
4. Grant microphone permission to Python app

### AI Chatbot Not Responding
**AI mode loads but no response**

**Solutions:**
1. Check `ai_config.json` exists with valid API key
2. Verify internet connection (for online APIs)
3. For Ollama: ensure running on `localhost:11434`
4. Check `robot.log` for API errors

### Robot Face Looks Wrong/Frozen
**Eye window doesn't update**

**Solutions:**
1. Windows: Check DPI scaling settings
2. Disable face tracking: `python main.py --camera -1`
3. Ensure Tkinter installed: `pip install tk`
4. Try restarting the program

### Linux/Mac Permission Errors
**"/dev/ttyACM0: Permission denied"**

**Solutions:**
```bash
# Linux
sudo usermod -a -G dialout $USER
# Log out and back in

# macOS - may need USB adapter drivers
```

### Pronunciation Training Not Working
**Records but says "no recognition"**

**Solutions:**
- Esperanto has limited STT support; robot uses phonetic fallback
- Speak clearly and pause between words
- Try Google STT option (requires internet)
- Motor skills vary; speech recognition isn't perfect!

---

## WRO Competition Alignment

This project perfectly embodies WRO 2026's **"Robots Meet Culture"** theme:

✅ **Robots Enhance Cultural Exchange**
- Teaches Esperanto, a language created for international peace
- Introduces Zamenhof's visionary story
- Promotes understanding across cultures

✅ **Inclusive & Accessible**
- Works with OR WITHOUT special hardware
- Friendly, non-intimidating face design
- Multiple learning styles (visual, audio, interactive)
- Free & open-source

✅ **Robotics with Educational Purpose**
- Real language learning outcomes
- LEGO hub as appropriate physical interface
- Advanced AI on laptop side
- Modular design allows endless expansion

✅ **Innovation in Interaction**
- Expressive facial emotions
- Gaze tracking (eyes follow viewer)
- Speech recognition & TTS
- AI chatbot with safety guardrails

✅ **Professional Quality**
- Clean, documented Python code
- Comprehensive documentation
- Extensible architecture
- Error handling for public safety

---

## Free Content Sources

### Vocabulary
- **Duolingo Esperanto** – [duolingo.com](https://www.duolingo.com/course/eo) (export word lists)
- **Lernu.net** – [lernu.net](https://www.lernu.net) (free interactive course)
- **Memrise** – Esperanto flashcard decks

### Poetry
- **Vikipedio (Esperanto Wikipedia)** – [eo.wikipedia.org](https://eo.wikipedia.org) (extensive poetry)
- **"La Espero"** – Esperanto national anthem (included)
- **Project Gutenberg** – Literature in Esperanto

### Audio & Music
- **YouTube** – Full Esperanto songs & lectures (download with yt-dlp)
- **Wikimedia Commons** – Free Esperanto audio
- **Archive.org** – Historical recordings

### General Reference
- **Esperanto League** – [esperanto.org](https://www.esperanto.org)
- **Universal Esperanto Association** – Organization & resources
- **Lernu.net** – Interactive lessons with audio

---

## License & Credits

Built for **WRO 2026 Future Innovators Competition**.
Celebrating Esperanto and the vision of international peace through language!

**Bonvenon! Ĝojon! 🤖✨**
