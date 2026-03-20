# WRO2026 — Esperanto Flashcard Robot 🤖

**LEGO SPIKE Prime · Python · BLE · SM-2 · wav2vec2 STT · Groq AI · gTTS · MP3**

Projekt na World Robot Olympiad 2026 — temat **"Robots Meet Culture"**.  
Robot chroni i udostępnia dziedzictwo kulturowe esperanto: uczy języka przez fiszki SM-2,
odtwarza poezję i muzykę, prowadzi rozmowę po esperanto z AI, oraz aktywnie zaprasza
przechodniów do interakcji (tryb Attract).

**Obszar WRO:** 1 (ochrona dziedzictwa) + 2 (współtworzenie z AI) + 3 (doświadczanie kultury)  
**Autor:** Wojciech Hałasa — [github.com/PantoYT](https://github.com/PantoYT)

---

## Jak to działa

```
[SPIKE Prime]  →  BLE  →  [PC: computer.py]
  przyciski                  ModeManager
  czujnik odl. (Port A)        ├─ FlashcardsMode   SM-2 + gTTS (EN + PL)
  silnik skanu (Port B)        ├─ MediaMode/poems  MP3 + adaptive queue
  LED 5×5                      ├─ MediaMode/music  MP3 + adaptive queue
  głośnik                      ├─ ConversationMode
                               │    wav2vec2 STT → Groq LLaMA3 → gTTS
                               └─ AttractMode
                                    TTS PL/EN + quiz + muzyka + poezja
```

---

## Tryby

| # | Tryb         | LED                        | Opis                                                                        |
|---|--------------|----------------------------|-----------------------------------------------------------------------------|
| 0 | FLASHCARDS   | 3 pełne wiersze (≡)        | Fiszki esperanto — algorytm SM-2 dobiera słowa wg. postępu                  |
| 1 | POEMS        | Cykliczne `. , ; : ! ? …`  | Poezja esperanto — MP3 + adaptacyjna kolejka + metadane przez TTS           |
| 2 | MUSIC        | Animowany korektor audio   | Muzyka esperanto — MP3 + adaptacyjna kolejka                                |
| 3 | CONVERSATION | Ikona dymku / mikrofonu    | Rozmowa po esperanto z AI (wav2vec2 STT + Groq + gTTS)                      |
| 4 | ATTRACT      | Pulsująca gwiazdka ✦       | Tryb wystawienniczy — aktywuje się po przebudzeniu, zaprasza do interakcji  |

---

## Sterowanie

### Menu (lewy przytrzymaj z dowolnego trybu)
| Przycisk | Akcja |
|----------|-------|
| Prawy    | Cykluj tryby → |
| Lewy     | Zatwierdź i wejdź |

### FLASHCARDS
| Przycisk          | Akcja |
|-------------------|-------|
| Prawy             | TAK — znam, SM-2 przesuwa dalej |
| Lewy              | NIE — nie znam, robot mówi definicję (EN + PL) |
| Prawy przytrzymaj | Powtórz definicję bez zmiany postępu |
| Lewy przytrzymaj  | Wróć do menu |

### POEMS / MUSIC
| Przycisk          | Akcja |
|-------------------|-------|
| Prawy             | Następny utwór (adaptacyjny dobór) |
| Lewy              | Poprzedni utwór |
| Prawy przytrzymaj | Odczytaj metadane (tytuł / autor / opis) przez TTS |
| Lewy przytrzymaj  | Wróć do menu |

### CONVERSATION
| Przycisk          | Akcja |
|-------------------|-------|
| Prawy             | Nagraj wypowiedź (maks. `audio_record_seconds` s) → AI odpowiada po esperanto |
| Lewy              | Anuluj nagrywanie / wyczyść historię konwersacji |
| Prawy przytrzymaj | Zmień poziom: A1 → B1 → C1 → A1 |
| Lewy przytrzymaj  | Wróć do menu |

#### Poziomy trudności
| Poziom | Zachowanie AI |
|--------|---------------|
| A1     | Krótkie zdania (maks. 10 słów), podstawowe słownictwo, korekta błędów |
| B1     | Normalne tempo, różnorodny słownik, dyskretna korekta |
| C1     | Pełna swoboda, idiomy, kulturowe referencje, bez uproszczeń |

> AI jest **zhardcodowane do esperanto** — system prompt wymusza odpowiedzi wyłącznie po esperanto.  
> Zmiana języka = edycja `_CONV_SYSTEM_PROMPTS` w `computer.py`.

### ATTRACT (tryb wystawienniczy)
Robot **sam** wchodzi w ten tryb po przebudzeniu ze snu. Losuje co ~25s jedną z sekwencji:

| Sekwencja       | Zawartość |
|-----------------|-----------|
| `word_quiz`     | Powitanie + "co znaczy X?" + pauza + odpowiedź EN + PL + CTA |
| `music_snippet` | Powitanie + 12s fragment muzyki esperanto + tytuł + CTA |
| `poem_snippet`  | Powitanie + 12s fragment poezji esperanto + tytuł + CTA |
| `fun_fact`      | Powitanie + ciekawostka o esperanto + bonus słówko + CTA |
| `full`          | Powitanie + quiz + muzyka lub poezja + ciekawostka + CTA |

| Przycisk    | Akcja |
|-------------|-------|
| Dowolny     | Instrukcja obsługi (PL + EN) → hub otwiera menu |

> Robot **nie przerywa** aktualnej sekwencji gdy ktoś odchodzi — kończy ją, a dopiero potem mówi pożegnanie i idzie spać.

---

## Instalacja od zera

### 1 — Python
Pobierz **Python 3.11+** ze strony https://python.org  
Przy instalacji zaznacz **"Add Python to PATH"**.

> Projekt testowany na Python 3.13 / 3.14. Działa na obu.

### 2 — Środowisko wirtualne i paczki
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
```

### 3 — Konfiguracja klucza API (opcja A — plik .env)
Utwórz plik `.env` w katalogu projektu:
```
GROQ_API_KEY=gsk_TUTAJ_WKLEJ_SWOJ_KLUCZ
```
Lub wpisz go bezpośrednio do `config.json` (opcja B — patrz sekcja Konfiguracja).

### 4 — Firmware Pybricks na SPIKE Prime
1. Wejdź na **https://code.pybricks.com**
2. Podłącz hub kablem USB
3. Kliknij ikonę ustawień → **Install Pybricks Firmware** → SPIKE Prime
4. Postępuj zgodnie z instrukcją na stronie

> Oryginalne oprogramowanie LEGO można przywrócić tą samą stroną.

### 5 — Konto Groq i klucz API (darmowe, bez karty)
1. Wejdź na **https://console.groq.com** i zarejestruj się (można przez Google)
2. Przejdź do **API Keys → Create API Key**
3. Skopiuj klucz — wklej do `.env` lub `config.json`

Klucz nie wygasa. Darmowy limit: ~14 000 żądań/dzień — wystarczy na wiele godzin rozmowy.

### 6 — Uruchomienie
```bash
# Włącz hub (środkowy przycisk), potem:
python computer.py
```
Program automatycznie połączy się z hubem przez BLE i wgra `hub.py`.

---

## Konfiguracja (config.json)

| Parametr              | Domyślnie                  | Opis |
|-----------------------|----------------------------|------|
| `groq_api_key`        | `""`                       | Klucz Groq (alternatywnie `GROQ_API_KEY` w `.env`) |
| `groq_model`          | `llama-3.3-70b-versatile`  | Model Groq |
| `whisper_model`       | `base`                     | Rozmiar modelu Whisper (fallback STT): `tiny` / `base` / `small` |
| `whisper_device`      | `cpu`                      | `cuda` (GPU) lub `cpu` |
| `audio_record_seconds`| `6`                        | Maks. długość jednej wypowiedzi [s] |
| `audio_activity_db`   | `-30`                      | Próg głośności mikrofonu [dB] |
| `audio_sample_rate`   | `16000`                    | Częstotliwość próbkowania mikrofonu [Hz] |
| `inactivity_timeout_s`| `60`                       | Czas do trybu snu [s] |
| `conv_history_turns`  | `8`                        | Liczba zachowywanych wymian konwersacji |
| `speaker_volume`      | `20`                       | Głośność głośnika huba (0–100) |

---

## STT — rozpoznawanie mowy esperanto

Tryb CONVERSATION używa dwuwarstwowego STT:

**Warstwa 1 — wav2vec2** (`cpierse/wav2vec2-large-xlsr-53-esperanto`)  
Model fine-tuned na Mozilla Common Voice esperanto. Pobierany automatycznie przy pierwszym uruchomieniu (~1 GB, cache w `~/.cache/huggingface`). Rozpoznaje znaki esperanto: ĉ, ĝ, ĥ, ĵ, ŝ, ŭ.

**Warstwa 2 — Whisper (fallback)**  
Jeśli wav2vec2 zwróci pusty string — używany jest Whisper z językiem włoskim (`it`), który ma najbliższą fonetykę do esperanto spośród obsługiwanych języków.

---

## Sleep / Wake

Po 60 sekundach braku aktywności hub przechodzi w tryb snu:
- LED pokazuje animację "Zzz"
- Silnik (Port B) obraca czujnik — wahadło ±45° (łącznie 90° zasięgu)
- Czujnik odległości (Port A) wykrywa kogoś < 200 cm → **WAKE → ATTRACT**
- Każde naciśnięcie przycisku lub głośny dźwięk przez mikrofon → reset timera

**Porty — zmień w `hub.py`:**
```python
DISTANCE_PORT   = Port.A   # czujnik odległości
SCAN_MOTOR_PORT = Port.B   # silnik skanowania

# Jeśli sensor jest fizycznie przesunięty od osi obrotu silnika:
SCAN_OFFSET_DEG = 15       # + = w prawo, - = w lewo
```
Jeśli sensory nie są podłączone — robot działa normalnie (inicjalizacja w `try/except`).

---

## Dodawanie treści

### Słówka (FLASHCARDS)
Edytuj `assets/flashcards/wordlist.json`:
```json
[
  { "word": "saluton", "translation": "hello / cześć" },
  { "word": "dankon",  "translation": "thank you / dziękuję" }
]
```
Pola `sr_*` i `next_review` są dodawane automatycznie.

### Muzyka / poezja
```bash
# Pobierz MP3 z YouTube (wymaga yt-dlp):
yt-dlp -x --audio-format mp3 -o "assets/music/%(title)s.mp3" "ytsearch1:SZUKANA FRAZA"
```
Dodaj wpis do `assets/music/music.json` (lub `poems.json`):
```json
{
  "id": "001",
  "filename": "plik.mp3",
  "title": "Tytuł",
  "artist": "Wykonawca",
  "year": 1900,
  "description": "Tekst czytany przez TTS po Prawym przytrzymaniu"
}
```
MP3 bez wpisu w JSON działa bez metadanych. Wpis bez MP3 jest pomijany z ostrzeżeniem.

---

## Autonomia

**SM-2 (fiszki)** — na podstawie historii odpowiedzi (`sr_ease`, `sr_interval`, `sr_repetitions`)
robot sam oblicza kiedy i które słowo pokazać. Słowa słabo znane wracają szybciej, dobrze znane — coraz rzadziej.

**Adaptacyjna kolejka mediów** — robot dobiera następny utwór ważąc:
- `play_count` — im częściej grany, tym mniejsza szansa na powtórkę
- `last_played` — bonus rośnie przez 7 dni od ostatniego odtworzenia
- `rating` — opcjonalne ręczne preferencje 1–5 w JSON

**Konwersacja AI** — LLM dostosowuje język do poziomu A1/B1/C1, zachowuje kontekst przez ostatnie `conv_history_turns` wymian.

**Attract** — 5 typów sekwencji losowanych bez powtórzeń, 15 powitań, 25 słówek, 8 ciekawostek. Robot nie przerywa sekwencji gdy ktoś odchodzi.

---

## Typowe błędy

| Błąd | Rozwiązanie |
|------|-------------|
| `Hub not ready — retrying` | Sprawdź firmware Pybricks, uruchom hub ponownie |
| `Cannot find package faster-whisper` | `pip install faster-whisper` |
| `CUDA not available` | Zmień `whisper_device` na `cpu` w config.json |
| `Groq HTTP 401` | Błędny klucz API — sprawdź `.env` lub `config.json` |
| `Groq HTTP 403 / 1010` | Cloudflare block — zainstaluj SDK: `pip install groq` |
| `Groq model decommissioned` | Zaktualizuj `groq_model` w `config.json` na `llama-3.3-70b-versatile` |
| `Groq HTTP 429` | Przekroczony dzienny limit Groq (~14 000 req) |
| `No speech detected` | Mów głośniej lub zmień `audio_activity_db` na `-40` |
| `No module named sounddevice` | `pip install sounddevice numpy` |
| `No module named dotenv` | `pip install python-dotenv` (opcjonalne) |
| `wav2vec2 load failed` | `pip install transformers torch` |

---

## Struktura projektu

```
WRO2026/
├── hub.py                   # Kod SPIKE Prime (Pybricks MicroPython)
├── computer.py              # Logika PC — tryby, SM-2, TTS, BLE, AI
├── config.json              # Konfiguracja (klucz API, parametry)
├── .env                     # Opcjonalny — zmienne środowiskowe (GROQ_API_KEY)
├── requirements.txt
├── README.md
├── LICENSE
└── assets/
    ├── flashcards/
    │   └── wordlist.json
    ├── poems/
    │   ├── poems.json
    │   └── *.mp3
    └── music/
        ├── music.json
        └── *.mp3
```

---

## Stack

| Technologia | Rola |
|-------------|------|
| LEGO SPIKE Prime + Pybricks | Hub, sensory, BLE |
| pybricksdev | BLE komunikacja PC ↔ hub |
| wav2vec2 (`cpierse/wav2vec2-large-xlsr-53-esperanto`) | STT — rozpoznawanie mowy esperanto (lokalnie) |
| faster-whisper | STT fallback (gdy wav2vec2 niedostępny) |
| Groq API + LLaMA 3.3 70B Versatile | LLM — odpowiedzi po esperanto (darmowy) |
| groq (Python SDK) | Klient API Groq (omija blokadę Cloudflare) |
| gTTS | TTS — synteza mowy (EN / PL) |
| pygame-ce | Odtwarzanie MP3 |
| sounddevice + numpy | Mikrofon + monitor aktywności audio |
| transformers + torch | Ładowanie modelu wav2vec2 |
| python-dotenv | Opcjonalne — ładowanie `.env` z kluczem API |
| SM-2 (własna impl.) | Spaced repetition dla fiszek |
| Python 3.11+ | Język PC |

---

## Changelog

### v1.3 — marzec 2026
- **NOWE** Tryb 4 — ATTRACT: robot aktywnie zaprasza przechodniów do interakcji (WRO Obszar 3)
  - 5 typów losowych sekwencji: quiz słówkowy, fragment muzyki, fragment poezji, ciekawostka, pełna
  - 15 powitań PL/EN, 25 słówek, 8 ciekawostek, 6 wariantów CTA i pożegnania
  - Robot nie przerywa sekwencji gdy ktoś odchodzi — kończy ją elegancko
  - Pulsująca animacja gwiazdki na LED
- **NOWE** STT wav2vec2 fine-tuned na esperanto (`cpierse/wav2vec2-large-xlsr-53-esperanto`)
  - Zastępuje Whisper jako główny STT w trybie CONVERSATION
  - Whisper pozostaje jako fallback
- **NOWE** Groq Python SDK — eliminuje błąd Cloudflare 1010 przy urllib
- **ZMIANA** Model Groq: `llama3-70b-8192` → `llama-3.3-70b-versatile` (poprzedni wycofany)
- **ZMIANA** Kąt skanu silnika: ±90° → ±45° (razem 90° zasięgu, bezpieczniejsze dla kabli)
- **ZMIANA** `SCAN_OFFSET_DEG` — korekcja offsetu montażu sensora bez ruszania silnikiem przy starcie
- **ZMIANA** Hub na starcie jedzie silnikiem do 0° (enkoder wie gdzie jest)
- **ZMIANA** Poems i Music w AttractMode — oba tryby mediów dostępne w sekwencjach attract

### v1.2 — marzec 2026
- **NOWE** Tryb 3 — CONVERSATION: Whisper STT + Groq LLaMA3 + gTTS, poziomy A1/B1/C1
- **NOWE** Sleep / Wake: czujnik odległości (Port A) + silnik skanowania (Port B)
- **NOWE** Monitor aktywności mikrofonu (reset timera snu przy głośnym dźwięku)
- **NOWE** Obsługa `.env` przez python-dotenv (klucz API poza kodem)
- **NOWE** `config.json` — wszystkie parametry bez edycji kodu
- **NOWE** Retry limit (3 próby) z checklistą błędów przy starcie
- **ZMIANA** `NUM_MODES` = 4, nowa ikona CV (dymek mowy) na LED

### v1.1 — marzec 2026
- Tryby FLASHCARDS, POEMS, MUSIC z menu
- SM-2 spaced repetition (własna implementacja)
- Adaptacyjna kolejka mediów (play_count, last_played, rating)
- gTTS EN + PL, pygame-ce zamiast pydub
- Animacje LED: statyczna karta (FC), cykliczne znaki (POEMS), korektor audio (MUSIC)
- BLE przez pybricksdev (zamiast serial)

### v1.0 — marzec 2026
- Podstawowe fiszki esperanto przez serial (pyserial)
- pyttsx3 TTS → zastąpione gTTS + pydub
- Proste ważenie słów przez wrong_count/correct_count → zastąpione SM-2

---

## Prezentacja dla jury WRO

**Problem:** Esperanto — język neutralny kulturowo, stworzony by łączyć narody — jest zagrożony
zapomnieniem. Mało materiałów edukacyjnych, mała dostępność dla nowych uczących się.

**Rozwiązanie:** Robot, który **aktywnie uczy** (nie tylko wyświetla), **rozmawia** po esperanto,
**zachowuje** kulturowe dziedzictwo (poezja, muzyka) i **wychodzi do ludzi** (tryb Attract).

**Autonomia — trzy warstwy:**
- SM-2 decyduje *kiedy* i *które* słowa pokazywać (historia odpowiedzi)
- Adaptacyjna kolejka decyduje *co* grać (statystyki odtworzeń)
- AI w trybie CONV decyduje *co* odpowiedzieć i dostosowuje poziom językowy

**Obszar WRO 1** — ochrona dziedzictwa: cyfrowe archiwum języka + kultury esperanto  
**Obszar WRO 2** — współtworzenie z AI: LLM jako partner językowy, nie tylko narzędzie  
**Obszar WRO 3** — doświadczanie kultury: tryb Attract aktywnie angażuje widzów  
**SDG 4** — dobra edukacja dla wszystkich  
**SDG 11** — ochrona dziedzictwa kulturowego