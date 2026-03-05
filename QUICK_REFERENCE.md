# 📋 Quick Reference Guide – Esperanto Robot

## Menu Structure

```
┌─ MAIN MENU (Start) ─────────────────┐
│                                     │
│  ▶ Flaŝkartoj (Flashcards)  💚      │  ← Button A to navigate
│    Poemoj (Poetry)           😊     │
│    Kantoj (Songs)            😊     │
│    Faktoj (Facts)            ⭕     │
│    Zamenhof (History)        ⬆️     │
│    Prononco (Pronunciation)  █       │
│    AI Asistanto (Chatbot)    ➡️     │  Button B to select
│                                     │
└─────────────────────────────────────┘
         │ Button B (select)
         ▼
    [Enter Mode]
         │ Button A (next/reveal) or B (play/confirm)
         │ Hold A to return to menu
         ▼
    [Mode Active]
```

## Button Controls (Hubbed Mode)

| Action | Effect |
|--------|--------|
| **Button A (left)** – Short Press | Next item / Reveal answer / Advance |
| **Button A (left)** – Long Hold | Return to menu from any mode |
| **Button B (right)** – Short Press | Confirm / Play / Accept answer |
| **Button B (right)** – Long Hold | Repeat last audio from any mode |

## Keyboard Controls (Hubless Mode)

| Key | Effect |
|-----|--------|
| **a** | Press Button A (short) – navigate/reveal |
| **b** | Press Button B (short) – confirm/play |
| **A** | Hold Button A (long) – back to menu |
| **B** | Hold Button B (long) – repeat audio |
| **q** | Quit program |

## Mode Reference

| Mode | Full Name | Uses | How to Use |
|------|-----------|------|-----------|
| 1️⃣ | Flaŝkartoj | `data/vocabulary/*.csv` | A=reveal/next, B=hear word |
| 2️⃣ | Poemoj | `data/poems/*.txt` | A=next poem, B=read aloud |
| 3️⃣ | Kantoj | `data/songs/*.mp3 .wav` | A=next, B=play |
| 4️⃣ | Faktoj | `data/facts/language_facts.txt` | A=next, B=repeat |
| 5️⃣ | Zamenhof | `data/facts/zamenhof_facts.txt` | A=next, B=repeat |
| 6️⃣ | Prononco | `data/vocabulary/*.csv` + mic | A=next word, B=record & check |
| 7️⃣ | AI Asistanto | OpenAI API / Ollama | A=clear history, B=ask question |

## File Locations

```
WRO2026/
├── data/
│   ├── vocabulary/
│   │   └── basic.csv              ← Edit for new words
│   ├── poems/
│   │   ├── La_Espero.txt          (provided)
│   │   └── YourPoem.txt           ← Add more poems
│   ├── songs/
│   │   └── song.mp3               ← Add .mp3 or .wav files
│   └── facts/
│       ├── language_facts.txt     ← Edit for new facts
│       └── zamenhof_facts.txt     ← Edit for history
├── laptop/
│   ├── main.py                    (entry point)
│   ├── serial_interface.py        (IDE communication)
│   ├── mode_manager.py            (state machine)
│   └── modules/
│       ├── flashcards.py
│       ├── poems.py
│       ├── songs.py
│       ├── facts.py
│       ├── zamenhof.py
│       ├── pronunciation.py
│       ├── ai_assistant.py
│       └── audio_player.py
├── hub_code/
│   └── hub_main.py                (upload to LEGO hub)
└── ai_config.template.json        (rename to ai_config.json)
```

## Quick Commands

```bash
# Test without hardware
python laptop/main.py --no-hub

# Run with LEGO hub (auto-detect port)
python laptop/main.py

# Specify COM port manually
python laptop/main.py --port COM3

# Disable face tracking
python laptop/main.py --camera -1

# Show all available COM ports
python -m serial.tools.list_ports
```

## CSV Format (Vocabulary)

**File:** `data/vocabulary/basic.csv`

```csv
esperanto,translation,notes
hundo,dog,common noun
kato,cat,common noun
domo,house,
```

- **Line 1:** Header (esperanto, translation, notes)
- **Line 2+:** Word pairs (any notes optional)
- Restart robot to load new files

## Esperanto Expressions

| English | Esperanto |
|---------|-----------|
| Hello | Saluton |
| Welcome | Bonvenon |
| Thank you | Dankon |
| Please | Bonvolu |
| How are you? | Kiel vi estas? |
| I love Esperanto | Mi amas Esperanton |
| Goodbye | Ĝis revido |
| Good luck | Sorĉo bone |

## Hub Icons (Available LED Displays)

```
HAPPY      SAD        HEART      SMILE      STALLED

😊         ☹️         ❤️         😄         ⚠️

CIRCLE     SQUARE     ARROW_UP   ARROW_DOWN ARROW_LEFT

⭕         █□        ⬆️         ⬇️         ⬅️

ARROW_RIGHT

➡️
```

## LED Colors (Hub Status Light)

- **BLUE** = Normal/Ready
- **GREEN** = Success/Active
- **YELLOW** = Warm/Caution
- **RED** = Error/Alert
- **ORANGE** = Info
- **WHITE** = Default

## Error Messages (What They Mean)

| Message | Cause | Fix |
|---------|-------|-----|
| "No serial port available" | Hub not detected | Check USB cable, try manual port |
| "Neniu vortaro trovita" | No vocabulary files | Add CSV files to `data/vocabulary/` |
| "Neniu poemo trovita" | No poems found | Add .txt files to `data/poems/` |
| "Neniu kanto trovita" | No songs found | Add .mp3/.wav to `data/songs/` |
| "requests not available" | Library not installed | `pip install requests` |
| "pyttsx3 not available" | TTS not installed | `pip install pyttsx3` |
| "AI API timeout" | Network too slow | Check internet, try different API |

## Troubleshooting Checklist

- [ ] **Can I even start the program?**
  - Run: `python main.py --no-hub`
  - Check console for error messages

- [ ] **Does the robot face appear?**
  - Should see Tkinter window with animated eyes
  - Works on any OS (Windows/Mac/Linux)

- [ ] **Does audio work?**
  - Test with: `python main.py --camera -1` (free resources)
  - Check system volume, speaker connected

- [ ] **Can I control it?**
  - Hubless: keyboard input works
  - Hubbed: hub buttons send JSON, laptop receives them

- [ ] **Do the modes load?**
  - Check `data/` directory has files
  - All modes fail gracefully if missing files

- [ ] **Is AI chatbot responsive?**
  - Have `ai_config.json` with API key or Ollama running?
  - Check `robot.log` for API errors

## Performance Tips

| Problem | Solution |
|---------|----------|
| Slow responses | `--camera -1` (disable face tracking) |
| Audio lag | Stop other programs, free up CPU |
| Face looks weird | Restart program or disable camera |
| Serial connection drops | Use better USB cable |
| AI takes forever | Use faster model in `ai_config.json` |

## Competition Prep

```
1 WEEK BEFORE:
  [ ] Test all modes in hubless mode
  [ ] Add all data files (vocabulary, poems, songs, facts)
  [ ] Verify AI chatbot works (if using)
  [ ] Create backup of entire folder

3 DAYS BEFORE:
  [ ] Test with physical hub connected
  [ ] Check button responsiveness
  [ ] Verify LED display works
  [ ] Test on different machines if possible

1 DAY BEFORE:
  [ ] Fresh reinstall of Python & dependencies
  [ ] Final content check
  [ ] Backups on USB drive (code + content)

DAY OF:
  [ ] Arrive early, test setup 30+ min before
  [ ] Test hubless mode first (no hardware risk)
  [ ] Then test hubbed mode
  [ ] Have laptop fully charged
  [ ] Have backup USB cable
```

## Support Resources

- **Python Documentation:** https://python.org/docs
- **Pybricks Documentation:** https://pybricks.com
- **Esperanto Resources:** https://lernu.net
- **WRO Competition:** https://wro-association.org

---

**Bonvenon al Esperanto Robot! Ĝoje uzu. 🤖✨**
