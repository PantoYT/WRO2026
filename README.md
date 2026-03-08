# WRO2026 - Esperanto Flashcard Robot 🤖

**LEGO SPIKE Prime + Python | BLE | SM-2 Spaced Repetition | TTS**

Projekt na World Robot Olympiad 2026 — temat "Robots Meet Culture".  
Robot uczy języka esperanto jako przykładu języka będącego dziedzictwem kulturowym (Obszar 1/2).

## Jak to działa

SPIKE Prime nasłuchuje przycisków i wysyła sygnały przez Bluetooth do komputera.  
Komputer dobiera słówka algorytmem SM-2, wymawia je przez TTS i zapisuje postępy.

```
[SPIKE Prime]  →  BLE  →  [PC: computer.py]
  lewy = NIE                  SM-2 pick_next()
  prawy = TAK                 gTTS → pygame
  prawy (hold) = DEFINE       wordlist.json
```

## Sterowanie

| Przycisk | Akcja |
|----------|-------|
| Prawy | TAK — znam słowo |
| Lewy | NIE — nie znam (+ definicja) |
| Prawy (przytrzymaj) | DEFINE — powtórz definicję |

## Flow fiszek

1. Robot mówi słowo po esperanto
2. Użytkownik myśli
3. **TAK** → SM-2 przesuwa słowo dalej
4. **NIE** → SM-2 cofa, robot mówi definicję (EN + PL)
5. **DEFINE** → definicja bez zmiany słowa, czeka na TAK/NIE

## SM-2

Algorytm powtórek rozproszonych wyciągnięty z projektu [Fiszki v5](https://github.com/PantoYT/Fiszki).  
Słowa powtarzane zbyt rzadko wracają szybciej, dobrze znane — coraz rzadziej.

## Stack

- **SPIKE Prime** + Pybricks MicroPython
- **pybricksdev** — BLE komunikacja
- **gTTS** — Google Text-to-Speech (EN + PL)
- **pygame-ce** — odtwarzanie audio
- Python 3.14

## Instalacja

```bash
pip install -r requirements.txt
py computer.py
```

Hub musi mieć wgrany firmware Pybricks: https://code.pybricks.com

## Struktura

```
WRO2026/
├── hub.py           # kod na SPIKE Prime (Pybricks)
├── computer.py      # logika PC — SM-2, TTS, BLE
├── wordlist.json    # słówka esperanto z postępem
└── requirements.txt
```

## Autor

Wojciech Hałasa — [github.com/PantoYT](https://github.com/PantoYT)