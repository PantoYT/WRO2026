import subprocess
import json
import random
import os
import sys
import tempfile
from datetime import datetime, timedelta

from gtts import gTTS
import pygame

# === KONFIGURACJA ===
WORDS_FILE = "wordlist.json"
PYTHON = sys.executable
# ====================


# --- Ładowanie / zapis ---

def load_words(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_words(words, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(words, f, ensure_ascii=False, indent=2)


# --- SM-2 (wyciągnięte z spaced_repetition.py z projektu Fiszki v5 https://github.com/PantoYT/Fiszki) ---

def sr_init(word):
    if 'sr_ease' not in word:
        word['sr_ease'] = 2.5
        word['sr_interval'] = 1
        word['sr_repetitions'] = 0
        word['next_review'] = datetime.now().isoformat()
    return word

def sr_update(word, is_correct):
    sr_init(word)
    quality = 4 if is_correct else 2

    ease = word['sr_ease']
    interval = word['sr_interval']
    reps = word['sr_repetitions']

    new_ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ease = max(1.3, new_ease)

    if quality < 3:
        new_reps = 0
        new_interval = 1
    else:
        new_reps = reps + 1
        if new_reps == 1:
            new_interval = 1
        elif new_reps == 2:
            new_interval = 3
        else:
            new_interval = int(interval * new_ease)

    word['sr_ease'] = new_ease
    word['sr_interval'] = new_interval
    word['sr_repetitions'] = new_reps
    word['next_review'] = (datetime.now() + timedelta(minutes=new_interval)).isoformat()

    if is_correct:
        word['correct_count'] = word.get('correct_count', 0) + 1
    else:
        word['wrong_count'] = word.get('wrong_count', 0) + 1

    return word


# --- Wybór następnego słowa ---

def pick_next(words):
    now = datetime.now()

    # 1. Słowa due (next_review <= teraz)
    due = [w for w in words if datetime.fromisoformat(sr_init(w)['next_review']) <= now]
    if due:
        return random.choice(due)

    # 2. Słowa nie zaczęte
    not_started = [w for w in words if w.get('sr_repetitions', 0) == 0]
    if not_started:
        return random.choice(not_started)

    # 3. Fallback - najwcześniejszy next_review
    return min(words, key=lambda w: w.get('next_review', ''))


# --- TTS ---

def _speak(text, lang):
    tts = gTTS(text=text, lang=lang)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
        tmp = f.name
    tts.save(tmp)
    pygame.mixer.init()
    pygame.mixer.music.load(tmp)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(100)
    pygame.mixer.quit()
    os.unlink(tmp)

def speak_word(word):
    _speak(word, lang='pl')

def speak_definition(current):
    translation = current.get('translation', '')
    parts = translation.split(' / ')
    en = parts[0].strip() if len(parts) > 0 else current.get('definition', '')
    pl = parts[1].strip() if len(parts) > 1 else ''
    print(f"Definicja: {en} | {pl}")
    _speak(en, lang='en')
    if pl:
        _speak(pl, lang='pl')


# --- Logika fiszek ---

def next_card(words):
    current = pick_next(words)
    print(f"Słowo: {current['word']}")
    speak_word(current['word'])
    return current

def handle(line, current, words, waiting_after_define):
    if line == "DEFINE":
        speak_definition(current)
        return current, True

    elif line in ("YES", "NO"):
        is_correct = (line == "YES")
        sr_update(current, is_correct)
        save_words(words, WORDS_FILE)

        if not is_correct and not waiting_after_define:
            # NIE bez wcześniejszego DEFINE - powiedz definicję
            speak_definition(current)

        current = next_card(words)
        return current, False

    return current, waiting_after_define


# --- Main ---

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    words = load_words(WORDS_FILE)

    print("Uruchamiam hub...")
    process = subprocess.Popen(
        [PYTHON, "-m", "pybricksdev", "run", "ble", "--wait", "hub.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"}
    )

    print("Czekam na połączenie z hubem...")
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        if "Searching" in line or "%" in line:
            print(f"[info] {line}")
            continue
        if line == "READY":
            break

    current = next_card(words)
    waiting_after_define = False

    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        print(f"Hub: {line}")
        current, waiting_after_define = handle(line, current, words, waiting_after_define)

if __name__ == "__main__":
    main()