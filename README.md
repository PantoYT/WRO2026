# WRO2026 — Esperanto Flashcard Robot 🤖

**LEGO SPIKE Prime + Python | BLE | SM-2 | Adaptive Queue | TTS | MP3**

Projekt na World Robot Olympiad 2026 — temat "Robots Meet Culture".
Robot chroni i udostępnia dziedzictwo kulturowe esperanto: uczy języka przez fiszki
SM-2, odtwarza poezję i muzykę esperanto z autonomiczną kolejką adaptacyjną.

**Obszar WRO:** 1 (ochrona dziedzictwa) + 2 (współtworzenie z AI)

---

## Jak to działa

SPIKE Prime nasłuchuje przycisków i wysyła sygnały przez Bluetooth do komputera.
Komputer obsługuje aktywny tryb — fiszki SM-2, odtwarzanie MP3, TTS.

```
[SPIKE Prime]  →  BLE  →  [PC: computer.py]
  przyciski                  ModeManager
                               ├─ FlashcardsMode  (SM-2 + gTTS)
                               ├─ MediaMode/poems (MP3 + adaptive queue)
                               └─ MediaMode/music (MP3 + adaptive queue)
```

---

## Autonomia

Robot podejmuje decyzje samodzielnie w dwóch warstwach:

**SM-2 (fiszki)** — algorytm powtórek rozproszonych. Na podstawie historii odpowiedzi
(`sr_ease`, `sr_interval`, `sr_repetitions`) sam oblicza kiedy i które słowo pokazać.
Słowa słabo znane wracają szybciej, dobrze znane — coraz rzadziej.

**Adaptacyjna kolejka mediów (muzyka/poezja)** — robot sam dobiera kolejny utwór
na podstawie trzech czynników, ważonych losowaniem:
- `play_count` — im częściej grany, tym mniejsza szansa na powtórkę
- `last_played` — bonus rośnie przez 7 dni od ostatniego odtworzenia
- `rating` — opcjonalne ręczne preferencje (1–5 w JSON)

Statystyki są zapisywane do JSON po każdym odtworzeniu i przetrwają restart.

---

## Tryby

| # | Tryb        | LED                           | Opis                                     |
|---|-------------|-------------------------------|------------------------------------------|
| 0 | FLASHCARDS  | 3 środkowe wiersze pełne      | nauka słówek esperanto (SM-2 + TTS)      |
| 1 | POEMS       | cykliczne znaki `. , ; : ! ?` | poezja esperanto z MP3 + metadane TTS    |
| 2 | MUSIC       | animowany audio-visualizer    | muzyka esperanto z MP3 + metadane TTS    |

---

## Sterowanie

### Menu wyboru trybu
Po starcie (i po każdym **lewym przytrzymaniu**) hub wchodzi w menu:
- **Prawy** — cykluj po trybach (ikona na LED)
- **Lewy** — zatwierdź i wejdź w tryb

### W trybie FLASHCARDS
| Przycisk            | Akcja                                        |
|---------------------|----------------------------------------------|
| Prawy               | TAK — znam słowo, SM-2 przesuwa dalej        |
| Lewy                | NIE — nie znam, robot mówi definicję (EN+PL) |
| Prawy (przytrzymaj) | Powtórz definicję bez zmiany słowa           |
| Lewy (przytrzymaj)  | Wróć do menu trybu                           |

### W trybach POEMS / MUSIC
| Przycisk            | Akcja                                        |
|---------------------|----------------------------------------------|
| Prawy               | Następny utwór (adaptacyjny dobór)           |
| Lewy                | Poprzedni utwór                              |
| Prawy (przytrzymaj) | Informacje o utworze (TTS, EN)               |
| Lewy (przytrzymaj)  | Wróć do menu trybu                           |

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
    │   ├── poems.json            # metadane + statystyki odtworzeń
    │   └── *.mp3
    └── music/
        ├── music.json            # metadane + statystyki odtworzeń
        └── *.mp3
```

### Format JSON (poems.json / music.json)

```json
{
  "id": "001",            // wymagane
  "filename": "plik.mp3", // wymagane
  "title": "...",
  "author": "...",
  "artist": "...",
  "year": 1887,
  "origin": "Poland",
  "language": "Esperanto",
  "genre": "...",
  "themes": ["..."],
  "description": "...",   // czytane przez TTS przy ACTION_HOLD
  "play_count": 0,        // zarządzane automatycznie
  "last_played": null,    // zarządzane automatycznie
  "rating": null          // opcjonalne: 1–5, wpływa na wagi kolejki
}
```

Pola `null` lub nieobecne są pomijane. MP3 bez wpisu w JSON działa bez metadanych.
Wpis bez MP3 jest pomijany z ostrzeżeniem.

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

# Dodaj wpis do assets/music/music.json
# play_count i last_played zostaw jako 0 / null — robot uzupełni sam
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