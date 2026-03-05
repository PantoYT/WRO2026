# 🤖 Esperanto Robot – Implementation & Deployment Guide

This guide is for developers, educators, and WRO teams looking to build, extend, and deploy the Esperanto Robot project.

---

## Contents
1. [Project Overview](#project-overview)
2. [Architecture Deep Dive](#architecture-deep-dive)
3. [Development & Testing](#development--testing)
4. [Adding New Content](#adding-new-content)
5. [Creating Custom Modes](#creating-custom-modes)
6. [Deployment Checklist](#deployment-checklist)
7. [Performance Optimization](#performance-optimization)
8. [Common Pitfalls & Solutions](#common-pitfalls--solutions)

---

## Project Overview

### What This Project Does
- **Educational robot** teaches Esperanto language and culture
- **Two-tier architecture**: LEGO hub (physical interface) + laptop (intelligent brain)
- **8 learning modes**: flashcards, poetry, songs, facts, history, pronunciation, AI chat
- **Two deployment modes**: hubbed (with hardware) and hubless (keyboard demo)

### Tech Stack
- **Hub firmware**: Pybricks MicroPython (LEGO Mindstorms 51515)
- **Laptop software**: Python 3.9+ with pygame, pyttsx3, opencv, requests
- **Communication**: USB serial (JSON over text)
- **UI**: Tkinter (simple, cross-platform)

### Why This Architecture?
✅ **Separation of concerns** – hub never needs updates, all logic on laptop
✅ **Hackable** – Python code is easy to modify
✅ **Modular** – add new learning modes as simple Python classes
✅ **Safe for public** – AI locked down to Esperanto topics only
✅ **Works offline** – most features work without internet

---

## Architecture Deep Dive

### Hub Side (Pybricks MicroPython)

**File:** `hub_code/hub_main.py`

**Responsibility:** Physical interface only

```
┌─────────────────────────────┐
│  LEGO 51515 Hub            │
│                             │
│  ▲ Button A (LEFT)         │
│  ■ Button B (RIGHT)        │
│                             │
│  ◻ ◻ ◻ ◻ ◻                   (5×5 LED display)
│  ◻ ◻ ◻ ◻ ◻                   
│  ◻ ◻ ◻ ◻ ◻                   
│  ◻ ◻ ◻ ◻ ◻                   
│  ◻ ◻ ◻ ◻ ◻                   
│                             │
│  ⚫ Status light            │
│                             │
│  ──────USB serial──────→   │
└─────────────────────────────┘
```

**Main Loop:**
1. Poll buttons every 50ms
2. Track button press duration
3. Send JSON messages on button release
4. Listen for commands from laptop
5. Control LED display and status light
6. Auto-sleep after 60 seconds idle

**Code Structure:**
- `send(msg)` – Serialize and send JSON to laptop via stdout
- `try_read_message()` – Non-blocking read from stdin
- `handle_command(cmd)` – Process commands from laptop
- `main()` – Main event loop

**Key Features:**
- ✅ Simple, readable, easy to debug
- ✅ No complex logic – pure I/O
- ✅ Robust – handles malformed JSON gracefully
- ✅ Efficient – 50ms polling is fine-grained enough

### Laptop Side (Python)

**File:** `laptop/main.py` (entry point)

**Responsibility:** All intelligence (state management, AI, audio, vision)

```
                           ┌──────────────────────────┐
                           │   main.py Entry Point    │
                           └─────────────┬────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
            ┌───────▼────┐      ┌───────▼──────┐      ┌──────▼──────┐
            │ Serial I/O  │      │ Mode Manager  │      │ Eye Animator│
            │             │      │ (state mach)  │      │ (Tkinter)   │
            │ USB↔HUB     │      │               │      │             │
            └──────────────┘      └────┬──────────┘      └──────────────┘
                                       │
                  ┌────────────────────┼────────────────────┐
                  │                    │                    │
          ┌───────▼────┐      ┌───────▼──────┐      ┌──────▼──────┐
          │ Flashcard   │      │ Poem         │      │ Audio        │
          │ Module      │      │ Module       │      │ Player       │
          │ (vocab CSV) │      │ (poems TXT)  │      │ (TTS/pygame) │
          └─────────────┘      └──────────────┘      └──────────────┘
                    
          ┌─────────────┐      ┌──────────────┐      ┌──────────────┐
          │ Song Mode   │      │ Fact Mode    │      │ Zamenhof     │
          │ (MP3/WAV)   │      │ (facts TXT)  │      │ Mode         │
          └─────────────┘      └──────────────┘      └──────────────┘
                    
          ┌─────────────┐      ┌──────────────┐
          │ Pronunc.    │      │ AI Assistant │
          │ Mode (STT)  │      │ (API calls)  │
          └─────────────┘      └──────────────┘
```

**Component Breakdown:**

| Component | File | Purpose |
|-----------|------|---------|
| **SerialInterface** | `serial_interface.py` | USB communication with hub |
| **ModeManager** | `mode_manager.py` | State machine, button dispatch |
| **FlashcardModule** | `modules/flashcards.py` | Vocabulary drills |
| **PoemModule** | `modules/poems.py` | Poetry recitation |
| **SongModule** | `modules/songs.py` | Music playback |
| **FactModule** | `modules/facts.py` | Language facts |
| **ZamenhofModule** | `modules/zamenhof.py` | Creator history |
| **PronounceModule** | `modules/pronunciation.py` | Mic-based training |
| **AIAssistantModule** | `modules/ai_assistant.py` | Chatbot (safe!) |
| **AudioPlayer** | `modules/audio_player.py` | TTS + audio |
| **EyeAnimator** | `vision/eye_animation.py` | Friendly face UI |
| **FaceTracker** | `vision/face_tracking.py` | Gaze tracking (optional) |

**Communication Flow:**
```
User presses button on hub
  ↓
HubSerial encodes as JSON: {"type": "BUTTON_A_PRESS", "hold": false}
  ↓
Laptop's SerialInterface reads the JSON
  ↓
ModeManager.handle_hub_message(msg) dispatches to active module
  ↓
Module's on_button_a() method is called
  ↓
Module may call:
  - audio.speak("text")
  - serial.send({"type": "SHOW_ICON", ...})
  - eyes.set_expression("happy")
```

---

## Development & Testing

### Setup Development Environment

```bash
# 1. Clone repo
git clone <url>
cd WRO2026

# 2. Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create data directory structure
mkdir -p data/{vocabulary,poems,songs,facts}
touch data/vocabulary/basic.csv
touch data/facts/{language_facts,zamenhof_facts}.txt
```

### Testing Without Hardware (Hubless Mode)

Perfect for development!

```bash
cd laptop
python main.py --no-hub
```

Then control via keyboard in the terminal:
```
a = button A (next)
b = button B (confirm)
A = hold A (back)
B = hold B (repeat)
q = quit
```

### Testing With Hub

1. Upload `hub_code/hub_main.py` to hub using Pybricks IDE
2. Connect hub via USB
3. Run: `python main.py`
4. System will auto-detect COM port

### Debugging Tips

**Enable debug logging:**
```bash
python main.py 2>&1 | tee debug.log
```

Check `robot.log` for all activity since startup.

**Test specific module:**
```python
# In Python REPL:
from laptop.modules.flashcards import FlashcardModule
from laptop.modules.audio_player import AudioPlayer

audio = AudioPlayer()
fc = FlashcardModule(None, audio, None)  # serial, audio, eyes (can be None)
fc.start()
fc.on_button_a()  # reveal translation
```

**Check serial connection:**
```bash
# List available COM ports
python -m serial.tools.list_ports

# Test serial communication
python main.py --port COM3 --no-hub
```

---

## Adding New Content

### Add Vocabulary (Flashcards)

**File:** `data/vocabulary/basic.csv`

Format: `esperanto,english,notes` (one per line)

```csv
hundo,dog,common noun
kato,cat,common noun
domo,house,
treege,tree,
```

Restart robot to auto-load new files.

### Add Poems

**Directory:** `data/poems/`

Create file: `data/poems/La_Espero.txt`

Content: Plain UTF-8 text of the poem

Filename (without `.txt`) becomes the title shown to user.

### Add Songs

**Directory:** `data/songs/`

Place `.mp3` or `.wav` files

System auto-discovers and plays them in order

### Add Facts

**File:** `data/facts/language_facts.txt`

Format: One fact per line

```
Esperanto uses a simple phonetic alphabet.
The language has only 16 grammar rules.
Esperanton was created by Ludwik Zamenhof in 1887.
```

Lines starting with `#` are comments

### Add Zamenhof Facts

**File:** `data/facts/zamenhof_facts.txt`

Same format as language facts

Note: Built-in fallback facts are provided

---

## Creating Custom Modes

Want to add a new learning activity? It's easy!

### Step 1: Create Module File

**File:** `laptop/modules/my_awesome_mode.py`

```python
"""
modules/my_awesome_mode.py
==========================
A custom learning mode for the Esperanto Robot.
"""

import logging

logger = logging.getLogger(__name__)

class MyAwesomeModule:
    """Custom learning mode."""
    
    def __init__(self, serial, audio, eyes):
        """
        Args:
            serial: SerialInterface instance (can be None)
            audio: AudioPlayer instance
            eyes: EyeAnimator instance
        """
        self.serial = serial
        self.audio = audio
        self.eyes = eyes
        
        # Initialize your mode state here
        self._state = None
    
    def start(self):
        """Called when entering this mode."""
        logger.info("MyAwesome mode started")
        self.eyes.set_expression("happy")
        self.audio.speak("Welcome to my awesome mode!")
        if self.serial:
            self.serial.send({"type": "SHOW_ICON", "icon": "HEART"})
    
    def stop(self):
        """Called when leaving this mode."""
        logger.info("MyAwesome mode stopped")
        # Cleanup code here
        pass
    
    def on_button_a(self):
        """Handle button A press (short)."""
        self.audio.speak("Button A!")
    
    def on_button_b(self):
        """Handle button B press (short)."""
        self.audio.speak("Button B!")
    
    def on_hold_a(self):
        """Optional: handle button A hold (long)."""
        self.audio.speak("Long press A!")
    
    def on_hold_b(self):
        """Optional: handle button B hold (long)."""
        self.audio.speak("Long press B!")
```

### Step 2: Register in Mode Manager

**File:** `laptop/mode_manager.py`

1. **Add to `Mode` enum:**
   ```python
   class Mode(Enum):
       # ... existing modes ...
       MY_AWESOME = auto()
   ```

2. **Add to `MENU_ITEMS` list:**
   ```python
   MENU_ITEMS = [
       # ... existing items ...
       (Mode.MY_AWESOME, "Mia Reĝimo", "HEART"),  # Label in Esperanto, icon
   ]
   ```

3. **Wire in `build_system()` function in `main.py`:**
   ```python
   from laptop.modules.my_awesome_mode import MyAwesomeModule
   
   # In build_system():
   my_awesome = MyAwesomeModule(serial=serial, audio=audio, eyes=eyes)
   manager.my_awesome = my_awesome
   ```

4. **Add mapping in `_get_module()` method:**
   ```python
   def _get_module(self, mode: Mode):
       return {
           # ... existing mappings ...
           Mode.MY_AWESOME: self.my_awesome,
       }.get(mode)
   ```

That's it! Your mode is now in the menu!

### Module Best Practices

✅ **Do:**
- Use `self.audio.speak()` for all speech (thread-safe)
- Use `self.eyes.set_expression()` for expressions
- Call `self.serial.send()` to control hub display
- Make button handlers non-blocking (use threading if needed)
- Log important events

❌ **Don't:**
- Don't call Tkinter directly
- Don't do long-running operations on main thread
- Don't assume hub is available (check `if self.serial`)
- Don't store file state across mode switches

---

## Deployment Checklist

### Pre-Competition Checklist

- [ ] **Code Quality**
  - [ ] All modules have docstrings
  - [ ] Python code follows PEP 8
  - [ ] No hardcoded paths (use relative paths)
  - [ ] Error handling for missing files

- [ ] **Data Files**
  - [ ] `data/vocabulary/*.csv` populated
  - [ ] `data/poems/*.txt` populated
  - [ ] `data/songs/*.mp3` or `*.wav` added
  - [ ] `data/facts/language_facts.txt` populated
  - [ ] `data/facts/zamenhof_facts.txt` populated

- [ ] **Hub Side**
  - [ ] `hub_code/hub_main.py` uploaded to hub
  - [ ] Hub LEDs working (test with different icons)
  - [ ] Buttons A & B responding correctly
  - [ ] USB cable is good quality (no drops)

- [ ] **Laptop Side**
  - [ ] `pip install -r requirements.txt` succeeds
  - [ ] All optional packages attempted
  - [ ] `python main.py` starts without errors
  - [ ] Face animation is smooth
  - [ ] Audio plays correctly

- [ ] **Integration**
  - [ ] Hubbed mode: buttons control activities
  - [ ] Hubless mode: keyboard works
  - [ ] Modes transition smoothly
  - [ ] No crashes on button spam
  - [ ] Clean shutdown (close window gracefully)

- [ ] **Documentation**
  - [ ] README.md is comprehensive
  - [ ] Code comments explain non-obvious logic
  - [ ] ai_config.json template provided
  - [ ] Log file generated

- [ ] **Safety**
  - [ ] AI module restricted to Esperanto topics
  - [ ] No prompt injection vulnerabilities
  - [ ] Serial errors don't crash program
  - [ ] Missing files don't crash program

### Competition Day

```bash
# 15 minutes before:
cd laptop
python main.py --no-hub  # test without hub

# 5 minutes before:
# 1. Plug hub into laptop
# 2. python main.py
# 3. Test each mode with buttons
# 4. Check audio output
# 5. Verify face animation
```

---

## Performance Optimization

### If Running Slowly

1. **Disable face tracking:**
   ```bash
   python main.py --camera -1
   ```

2. **Reduce model complexity** (if using AI):
   - Edit `ai_config.json`
   - Use faster model (e.g., "tinyllama" instead of "llama3")

3. **Limit log verbosity:**
   ```python
   # In laptop/main.py:
   logging.basicConfig(level=logging.WARNING)  # reduce to WARNING
   ```

4. **Use faster TTS:**
   ```python
   # In laptop/modules/audio_player.py:
   engine.setProperty("rate", 200)  # faster speech
   ```

### If Audio is Laggy

1. Check system CPU usage
2. Disable face tracking
3. Stop other programs
4. Increase pygame buffer size

### Hub Responsiveness

The hub is already optimized (50ms polling from native C++ Pybricks code).
If buttons feel slow, it's a laptop issue – check CPU usage.

---

## Common Pitfalls & Solutions

### Problem: "ModuleNotFoundError: No module named 'pyttsx3'"

**Solution:**
```bash
pip install -r requirements.txt
```

If that fails on `pyaudio`:
```bash
pip install pyttsx3 pygame requests
# Offline TTS will work, just not the mic for pronunciation
```

### Problem: Serial Port Not Found

**Windows:**
1. Open Device Manager
2. Look for "COM3" or similar under "Ports"
3. Run: `python main.py --port COM3`

**Linux/Mac:**
```bash
ls /dev/ttyACM*  # or /dev/tty.usbmodem*
python main.py --port /dev/ttyACM0
```

### Problem: Hub Connected But Program Says "No Hub"

**Check:**
1. Is hub actually running code? (LED should be on)
2. Is USB cable connected to laptop?
3. Try different USB port
4. Update Pybricks firmware
5. Manually specify port: `python main.py --port COM3`

### Problem: AI Module Says "No API Key"

**Solution:**
```bash
cp ai_config.template.json ai_config.json
# Edit ai_config.json and add your API key
```

Options:
- **Groq** (recommended): Sign up free at groq.com
- **OpenRouter**: Sign up at openrouter.ai
- **Ollama**: Run locally (no API key needed)

### Problem: Face Looks Frozen/Weird

**Try:**
1. Close and reopen
2. Disable webcam: `python main.py --camera -1`
3. Check if another program is using webcam
4. Update opencv: `pip install --upgrade opencv-python`

### Problem: Microphone Not Working in Pronunciation Mode

**Check:**
1. System volume is up
2. Microphone is plugged in
3. System microphone works (test in voice recorder)
4. Install PyAudio:
   ```bash
   pip install pyaudio
   ```

---

## Next Steps

- ✅ Run in hubless mode first (no hardware)
- ✅ Test all modules one by one
- ✅ Add your own content (poems, songs, facts)
- ✅ Create custom learning modes
- ✅ Upload to hub when ready
- ✅ Deploy at competition!

**Good luck! Bonvenon! 🤖✨**
