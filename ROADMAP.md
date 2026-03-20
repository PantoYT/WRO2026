# ROADMAP — WRO 2026 Esperanto Flashcard Robot

> Ostatnia aktualizacja: marzec 2026 · Wersja bieżąca: v1.3
> Uwaga: sekcja "Poprawki techniczne hub.py" dodana po przeglądzie kodu — są to rzeczy działające, ale podatne na problemy przy dłuższym użytkowaniu.

---

## Ocena aktualnego stanu vs wymagania WRO

### Co już spełnia regulamin

**Wymagania techniczne:**
- Wiele mechanizmów i czujników: czujnik ultradźwiękowy (Port A), silnik skanowania (Port B), głośnik, matryca LED 5×5 — wszystkie sterowane z jednego huba
- Dwuwęzłowa architektura: SPIKE Prime (hub.py) + PC (computer.py) przez BLE — spełnia wymóg "jednego lub więcej kontrolerów"
- Autonomiczne podejmowanie decyzji w czasie rzeczywistym — trzy niezależne warstwy:
  - SM-2 oblicza kiedy i które słowo pokazać na podstawie historii odpowiedzi
  - Adaptacyjna kolejka mediów dobiera utwór na podstawie play_count, last_played, rating
  - LLM w ConversationMode odpowiada i dostosowuje poziom języka do każdej konkretnej wypowiedzi użytkownika — to jest ciągła adaptacja w czasie rzeczywistym, nie sekwencja z góry zaplanowana

**Obszary tematyczne:**
- Obszar 1 (ochrona dziedzictwa): cyfrowe archiwum poezji i muzyki esperanto w formacie MP3 + JSON z metadanymi; wordlist.json jako cyfrowy słownik esperanto — digitalizacja żywego języka zagrożonego marginalizacją
- Obszar 2 (współtworzenie ludzie–roboty–AI): ConversationMode to realny dialog, nie Q&A — LLM jest partnerem językowym, historia konwersacji jest zachowywana, poziom jest dostosowywany do postępów użytkownika
- Obszar 3 (doświadczanie kultury): AttractMode aktywnie angażuje przechodniów przez quizy, fragmenty poezji i muzyki, ciekawostki; tryb POEMS i MUSIC z metadanymi czytanymi przez TTS

**Realny problem:**
Esperanto jest jedynym szeroko stosowanym planowanym językiem stworzonym z myślą o równym dialogu między kulturami — żaden naród nie ma w nim przewagi. Mimo 130+ lat istnienia i ~2 milionów mówiących, dostęp do materiałów edukacyjnych jest rozproszony i nierówny. Robot adresuje ten problem bezpośrednio: uczy języka, przechowuje kulturę, rozmawia — w jednym urządzeniu, bez internetu dla podstawowych funkcji.

### Co wymaga uzupełnienia przed zawodami

Poniżej lista punktów pogrupowana według priorytetu i nakładu pracy.

---

## Priorytet WYSOKI — przed zawodami

### 1. Konsultacja z praktykami kultury (0 linii kodu — wymagane przez regulamin)

WRO explicite wymaga, żeby zespół "porozmawiał z artystami, konserwatorami, historykami lub członkami społeczności". Bez tego jury może uznać projekt za czysto techniczny, bez zakorzenienia w realnym problemie.

**Co zrobić:**
Skontaktuj się z polskim kołem esperanto (Polskie Towarzystwo Esperantystów — pte.pl) lub lokalnym esperantystą. Wystarczy jedna rozmowa, mail, albo krótki wywiad. Zapytaj:
- Czy osoby uczące się esperanto mają trudności z dostępem do materiałów?
- Jakich słów/tematów brakuje w popularnych kursach?
- Czy istnieje ryzyko, że nagrania poezji/muzyki esperanto przepadną?

Odpowiedzi wpleć do prezentacji jako "konsultację z praktykiem". Jeden akapit wystarczy.

**Czas:** 1–2 dni (mail + oczekiwanie na odpowiedź)

---

### 2. Kontekstowe przejście z CONVERSATION do POEMS/MUSIC (małe, duży efekt)

**Problem:** Jury może zapytać czy robot naprawdę reaguje na kontekst kulturowy, czy tylko odpowiada na pytania.

**Propozycja:** Jeśli LLM w odpowiedzi wykryje słowo kluczowe związane z kulturą esperanto (poezja, muziko, kanto, literaturo, Zamenhof), robot może zaproponować głosem przejście do trybu POEMS lub MUSIC. Użytkownik potwierdza prawym przyciskiem.

**Implementacja — `computer.py`, klasa `ConversationMode._listen_and_reply`:**

Po linii `reply = _groq_chat(...)` dodaj:

```python
# Kontekstowe przejście do trybu mediów
_CULTURE_KEYWORDS = ["poezio", "kanto", "muziko", "poemo", "literaturo",
                     "kult", "zamenhof", "libro", "arte"]
if any(kw in reply.lower() for kw in _CULTURE_KEYWORDS):
    _speak("Ĉu vi volas aŭdi muzikon aŭ poezion en Esperanto? Premu la dekstran butonon.", lang="en")
    self._pending_media_offer = True  # obsłuż w on_yes()
```

W `on_yes()` dodaj obsługę `self._pending_media_offer` — jeśli True, wyślij sygnał `MODE:1` (POEMS) lub `MODE:2` (MUSIC) do ModeManagera.

**Czas:** 2–3 godziny

---

### 3. Wzmocnienie narracji w README / prezentacji (0 kodu)

Sekcja "Prezentacja dla jury WRO" w README jest dobra, ale można ją wzmocnić w dwóch miejscach:

**Dodaj do sekcji Obszar 1:**
> Słownik esperanto (wordlist.json) jest budowany ręcznie lub przez skan istniejących słowników (np. Plena Ilustrita Vortaro) — to cyfrowe repozytorium żywego języka, który nie ma instytucji państwowej dbającej o jego zachowanie.

**Dodaj wzmiankę o SDG 17** (partnerstwo na rzecz celów) — robot łączy technologię (AI, robotyka) z dziedzictwem kulturowym i edukacją, co jest dokładnie duchem SDG 17.

**Czas:** 30 minut

---

## Priorytet ŚREDNI — wzmacniają ocenę autonomii

### 4. Skan słownika jako źródło wordlist (opcjonalne, ale mocny argument)

**Problem:** Aktualnie wordlist.json jest tworzony ręcznie. Jeśli możliwe jest zaimportowanie słów z istniejącego słownika esperanto (np. z pliku tekstowego PVZ lub CSV), robot staje się narzędziem digitalizacji — co bezpośrednio trafia w Obszar 1.

**Propozycja:** Dodaj skrypt `tools/import_wordlist.py` który:
1. Wczytuje plik TSV/CSV (słowo ↔ tłumaczenie)
2. Deduplikuje względem istniejącego wordlist.json
3. Dodaje nowe wpisy bez nadpisywania postępu SM-2

Skrypt nie musi być częścią robota — wystarczy że istnieje i jest opisany w README jako narzędzie digitalizacji.

```python
# tools/import_wordlist.py — szkielet
import json, csv, sys
from pathlib import Path

def import_tsv(tsv_path: str, wordlist_path: str):
    existing = json.loads(Path(wordlist_path).read_text(encoding="utf-8"))
    existing_words = {e["word"] for e in existing}
    added = 0
    with open(tsv_path, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if len(row) < 2: continue
            word, translation = row[0].strip(), row[1].strip()
            if word and word not in existing_words:
                existing.append({"word": word, "translation": translation})
                existing_words.add(word)
                added += 1
    Path(wordlist_path).write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dodano {added} nowych słów.")

if __name__ == "__main__":
    import_tsv(sys.argv[1], "assets/flashcards/wordlist.json")
```

**Czas:** 1–2 godziny

---

### 5. Statystyki sesji mówione przez robota (mały WOW-efekt dla jury)

Przy wyjściu z trybu FLASHCARDS (lub na żądanie przez ACTION_HOLD w menu) robot mógłby powiedzieć głosem: *"W tej sesji odpowiedziałeś na 12 pytań. 8 poprawnych, 4 błędne. Najsłabsze słowo: pomo."*

To bezpośredni dowód na to, że robot *analizuje dane* i podejmuje decyzje — mocny argument dla kryterium autonomii.

**Implementacja:** W `FlashcardsMode` dodaj liczniki `session_correct` i `session_wrong` oraz `session_weak_word` (słowo z największym wrong_count w tej sesji). Odczytaj je w `on_sleep()` lub przez nowy sygnał `STATS`.

**Czas:** 2–3 godziny

---

## Priorytet NISKI — polish przed finałem

### 6. Esperanto TTS zamiast angielskiego

Aktualnie `_speak(word, lang="pl")` wypowiada słowo esperanto głosem polskim, a `_speak(reply, lang="en")` — odpowiedzi LLM głosem angielskim. gTTS obsługuje `lang="eo"` (esperanto) — warto przetestować jakość i ewentualnie przełączyć odpowiedzi ConversationMode na `lang="eo"`.

```python
# Zmiana w ConversationMode._listen_and_reply, ostatnia linia:
_speak(reply, lang="eo")  # zamiast lang="en"
```

Jeśli jakość jest zła — zostaw `"en"`. Ale jeśli działa, jest to silny argument: *robot mówi po esperanto*.

**Czas:** 30 minut (test + ewentualna zmiana)

---

### 7. Pełna dokumentacja struktury assets/

Dodaj do README przykładowe pliki `poems.json` i `music.json` z co najmniej 2–3 wpisami każdy, żeby jury mogło zobaczyć jak działa archiwum kulturowe. Opisz skąd pobierać legalnie muzykę esperanto (np. Jamendo, Vinilkosmo).

**Czas:** 1 godzina

---

## Poprawki techniczne hub.py — stabilność

Te punkty nie zmieniają logiki ani funkcji — tylko usuwają potencjalne problemy przy dłuższym użytkowaniu. Wszystkie są małe i niezależne od siebie.

### H1. Literówka w wordliście attract (PILNE — jury może zobaczyć)

W `computer.py`, lista `_ATTRACT_TEASER_WORDS`:
```python
("riди",  "to laugh", "śmiać się"),  # ← cyrylica zamiast esperanto!
```
Poprawka:
```python
("ridi",  "to laugh", "śmiać się"),
```

**Czas:** 30 sekund.

---

### H2. Silnik skanowania — eliminacja szarpania

Aktualnie `_scan_step()` wywołuje `run_target()` co ~100ms nawet jeśli cel się nie zmienił, co powoduje ciągłe restartowanie ruchu silnika.

```python
# Dodaj na górze pliku:
_scan_target = None

def _scan_step():
    global _scan_idx, _scan_target
    if not _has_motor:
        return
    try:
        physical_target = _SCAN_LOGICAL[_scan_idx] + SCAN_OFFSET_DEG
        angle = _scan_motor.angle()
        if abs(angle - physical_target) <= 8:
            _scan_idx = 1 - _scan_idx
            physical_target = _SCAN_LOGICAL[_scan_idx] + SCAN_OFFSET_DEG
        if _scan_target != physical_target:          # ← tylko gdy cel się zmienia
            _scan_target = physical_target
            _scan_motor.run_target(SCAN_SPEED, physical_target, wait=False)
    except Exception:
        pass
```

**Czas:** 15 minut.

---

### H3. Czujnik odległości — filtr ostatniej poprawnej wartości

Czujnik ultradźwiękowy bywa niestabilny i może zwracać `None` lub skrajne wartości. Bez filtra robot może chwilowo "nie widzieć" osoby stojącej przed nim.

```python
_last_distance = None

def _read_distance_cm():
    global _last_distance
    if not _has_distance:
        return None
    try:
        d = _distance.distance()
        if d is not None:
            _last_distance = d / 10
    except Exception:
        pass
    return _last_distance
```

**Czas:** 10 minut.

---

### H4. Literówka Whisper fallback — język "it" zamiast auto

W `computer.py`, metoda `_listen_and_reply`:
```python
segments, info = whisper.transcribe(audio_float, language="it")
```
Włoski (`"it"`) był obejściem fonetycznym — ale powoduje że Whisper może odrzucać poprawne esperanto. Lepiej użyć autodetekcji:
```python
segments, info = whisper.transcribe(audio_float, language=None)
```
Jeśli autodetekcja działa gorzej w praktyce — zostaw `"it"`, ale warto przetestować.

**Czas:** 5 minut + test.

---

### H5. Statystyki sesji FLASHCARDS (WOW-efekt dla jury)

Robot aktualnie nie informuje użytkownika o postępach. Dodanie głosowego podsumowania sesji to bezpośredni, widoczny dowód na to że robot analizuje dane użytkownika.

W `FlashcardsMode.__init__` dodaj:
```python
self.session_correct = 0
self.session_wrong   = 0
```

W `on_yes()` i `on_no()` inkrementuj liczniki. W `on_sleep()` lub po przejściu do menu:
```python
if self.session_correct + self.session_wrong > 0:
    weak = max(self.words, key=lambda w: w.get("wrong_count", 0))
    _speak(
        f"Session summary: {self.session_correct} correct, "
        f"{self.session_wrong} wrong. "
        f"Weakest word: {weak['word']}.",
        lang="en"
    )
    self.session_correct = 0
    self.session_wrong   = 0
```

**Czas:** 1–2 godziny.

---

## Stan spełnienia wymagań — po wdrożeniu roadmapy

| Kryterium WRO | Przed | Po |
|---|---|---|
| Wiele mechanizmów/czujników | ✅ | ✅ |
| Autonomiczne decyzje w czasie rzeczywistym | ✅ | ✅ wzmocnione pkt 2+5 |
| Obszar 1 — ochrona dziedzictwa | ✅ częściowe | ✅ mocne (pkt 3+4) |
| Obszar 2 — współtworzenie z AI | ✅ | ✅ |
| Obszar 3 — doświadczanie kultury | ✅ | ✅ |
| Realny problem i wpływ społeczny | ✅ częściowe | ✅ (pkt 1+3) |
| Konsultacja z praktykami kultury | ❌ | ✅ (pkt 1) |
| SDG | SDG 4, 11 | SDG 4, 11, 17 |

---

## Kolejność implementacji (sugerowana)

1. **Teraz (30 min):** Literówka `riди` → `ridi` (H1) + Whisper lang=None test (H4) -- zrobione
2. **Dziś/jutro:** Filtr czujnika (H3) + fix skanowania (H2) + konsultacja esperantysta w prezentacji (pkt 1)
3. **Ten tydzień:** Statystyki sesji (H5) + kontekstowe przejście CONV → MEDIA (pkt 2) + esperanto TTS test (pkt 6)
4. **Następny tydzień:** Skrypt importu słownika (pkt 4)
5. **Przed zawodami:** Wzmocnienie README/prezentacji (pkt 3+7)