# Roadmap — WRO2026 Esperanto Flashcard Robot

## Obecny stan (prototyp)

Pełna logika huba (`hub.py`) — menu, tryby, animacje LED, BLE.
Logika PC (`computer.py`) — SM-2, TTS, odtwarzanie MP3.
Sterowanie: przyciski fizyczne na SPIKE Prime.

---

## Planowane: Warstwa AI (multimodal agent)

### Koncepcja

Przyciski fizyczne zostaną **uzupełnione** (nie zastąpione) przez agenta AI,
który słyszy i widzi użytkownika i autonomicznie reaguje w czasie rzeczywistym.

```
[Kamera / telefon]  ──┐
                       ├──► [agent.py]  ──► [computer.py ModeManager]
[Mikrofon]          ──┘
                            ▲
                     LLM (vision + audio)
                     lokalne lub API
```

### Wejście

| Źródło | Technologia | Uwagi |
|--------|-------------|-------|
| Mikrofon | Whisper (OpenAI, open source) | STT lokalnie |
| Kamera | Phone Link / kamera USB | obraz do LLM |

### LLM

| Środowisko | Model | Uwagi |
|------------|-------|-------|
| Development (RTX 3060) | Ollama + LLaVA / moondream | lokalnie, bez internetu |
| Konkurs (laptop bez GPU) | API (Gemini / GPT-4o) + hotspot | niska latencja |

Agent dostaje ścisły system prompt z listą dozwolonych akcji — nie może robić
nic poza zdefiniowanym zestawem komend. Żadnych "wolnych" odpowiedzi.

### Komendy głosowe (planowane)

| Komenda | Akcja |
|---------|-------|
| "tak" / "znam" / "yes" | YES (fiszki) |
| "nie" / "no" | NO (fiszki) |
| "następny" / "next" | następny utwór |
| "poprzedni" / "back" | poprzedni utwór |
| "pauza" / "pause" | pauza/play |
| "info" / "powiedz więcej" | ACTION_HOLD (TTS opis) |
| "menu" | powrót do menu trybów |

### Reakcja na obraz (planowane)

Agent analizuje twarz/gestykulację użytkownika i może np.:
- wykryć że użytkownik się waha → automatycznie powtórzyć definicję
- wykryć gest "kciuk w górę/dół" jako alternatywę dla przycisku
- dostosować tempo nauki do widocznego poziomu skupienia

---

## Planowane: Czujniki fizyczne

Zakomentowane w `hub.py`, zostaną aktywowane gdy dostępny sprzęt:

- **Motor** (Port A) — fizyczny przycisk/dźwignia jako alternatywa sterowania
- **ColorSensor** (Port B) — wykrywanie gestów / kart kolorowych jako wejście

---

## Harmonogram (orientacyjny)

| Tydzień | Cel |
|---------|-----|
| 1–2 | Whisper STT → komendy głosowe → `computer.py` |
| 3–4 | Integracja vision LLM (moondream lokalnie) |
| 5–6 | System prompt, limity, testy autonomii |
| 7 | Czujniki fizyczne (motor + kolor) |
| 8 | Testy końcowe, fallback API na konkurs |

---

## Uwagi techniczne

- Agent działa jako **osobny proces** (`agent.py`), komunikuje się z `computer.py` przez kolejkę / socket — żeby awaria AI nie zawieszała logiki robota
- Przyciski fizyczne **zawsze działają** niezależnie od stanu agenta (redundancja)
- Na konkursie: hotspot z telefonu jako backup internetu dla API