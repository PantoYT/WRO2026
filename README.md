# WRO2026 — Esperanto Flashcard Robot 🤖

**LEGO SPIKE Prime + Python | BLE | SM-2 | TTS | MP3**

Projekt na World Robot Olympiad 2026 — temat "Robots Meet Culture" (Obszar 1/2).
Robot uczy języka esperanto jako przykładu żywego dziedzictwa kulturowego, a także
odtwarza muzykę i poezję w języku esperanto.

---

## Jak to działa

SPIKE Prime nasłuchuje przycisków i wysyła sygnały przez Bluetooth do komputera.
Komputer obsługuje aktywny tryb — fiszki SM-2, odtwarzanie MP3, TTS.

```
[SPIKE Prime]  →  BLE  →  [PC: computer.py]
  przyciski                  ModeManager
                               ├─ FlashcardsMode  (SM-2 + gTTS)
                               ├─ MediaMode/poems (MP3 + metadata)
                               └─ MediaMode/music (MP3 + metadata)
```

---

## Tryby

| # | Tryb        | LED                        | Opis                              |
|---|-------------|----------------------------|-----------------------------------|
| 0 | FLASHCARDS  | 3 środkowe wiersze pełne   | nauka słówek esperanto (SM-2+TTS) |
| 1 | POEMS       | cykliczne znaki `. , ; : ! ?` | odtwarzanie poezji z MP3       |
| 2 | MUSIC       | animowany audio-visualizer | odtwarzanie muzyki z MP3          |

---

## Sterowanie

### Menu wyboru trybu
Po starcie (i po każdym **lewym przytrzymaniu**) hub wchodzi w menu:
- **Prawy** — cykluj po trybach (widać ikonę na LED)
- **Lewy** — zatwierdź i wejdź w tryb

### W trybie FLASHCARDS
| Przycisk | Akcja |
|----------|-------|
| Prawy | TAK — znam słowo, SM-2 przesuwa dalej |
| Lewy | NIE — nie znam, robot mówi definicję (EN + PL) |
| Prawy (przytrzymaj) | Powtórz definicję bez zmiany słowa |
| Lewy (przytrzymaj) | Wróć do menu trybu |

### W trybach POEMS / MUSIC
| Przycisk | Akcja |
|----------|-------|
| Prawy | Następny utwór |
| Lewy | Poprzedni utwór |
| Prawy (przytrzymaj) | Informacje o utworze (TTS, EN) |
| Lewy (przytrzymaj) | Wróć do menu trybu |

---

## Struktura projektu

```
WRO2026/
├── hub.py                        # kod na SPIKE Prime (Pybricks MicroPython)
├── computer.py                   # logika PC — tryby, SM-2, TTS, BLE
├── requirements.txt
├── LICENSE
└── assets/
    ├── flashcards/
    │   └── wordlist.json         # słówka esperanto z postępem SM-2
    ├── poems/
    │   ├── poems.json            # metadane poezji
    │   └── *.mp3                 # pliki audio
    └── music/
        ├── music.json            # metadane muzyki
        └── *.mp3                 # pliki audio
```

### Format JSON (poems.json / music.json)

```json
{
  "id": "001",           // wymagane
  "order": 1,            // kolejność odtwarzania (opcjonalne)
  "filename": "plik.mp3",// wymagane — dokładna nazwa pliku
  "title": "...",        // opcjonalne
  "author": "...",       // opcjonalne
  "artist": "...",       // opcjonalne
  "year": 1887,          // opcjonalne
  "origin": "Poland",    // opcjonalne
  "language": "...",     // opcjonalne
  "genre": "...",        // opcjonalne
  "themes": ["..."],     // opcjonalne
  "description": "..."   // opcjonalne — czytane przez TTS przy ACTION_HOLD
}
```

Pola `null` lub nieobecne są pomijane — skrypt się nie wywali.
MP3 bez wpisu w JSON działa, ale bez metadanych. Wpis bez MP3 jest pomijany z ostrzeżeniem.

---

## SM-2 (Spaced Repetition)

Algorytm powtórek rozproszonych z projektu [Fiszki v5](https://github.com/PantoYT/Fiszki).
Słowa słabo znane wracają szybciej, dobrze znane — coraz rzadziej.

---

## Instalacja

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python computer.py
```

Hub musi mieć firmware Pybricks: https://code.pybricks.com
`hub.py` jest wgrywany automatycznie przez pybricksdev po BLE.

### Dodawanie muzyki / poezji

```bash
# Pobierz MP3 z YouTube
yt-dlp -x --audio-format mp3 -o "assets/music/%(title)s.mp3" "ytsearch1:SZUKANA FRAZA"

# Następnie dodaj wpis do assets/music/music.json
```

---

## Stack

- **LEGO SPIKE Prime** + Pybricks MicroPython
- **pybricksdev** — BLE komunikacja
- **gTTS** — Google Text-to-Speech (EN + PL)
- **pygame-ce** — odtwarzanie MP3
- **yt-dlp** — pobieranie audio (opcjonalne)
- Python 3.13+

---

## Autor

Wojciech Hałasa — [github.com/PantoYT](https://github.com/PantoYT)