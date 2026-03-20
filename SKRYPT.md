# Skrypt prezentacji — WRO 2026 Future Innovators
# „Esperanto Robot" — jury WRO, ~5 minut

> **Legenda:**
> `[DEMO]` = moment w którym włączasz/pokazujesz robota na żywo
> `[SLAJD]` = zmiana slajdu
> *(kursywa)* = wskazówka, nie mów tego głośno
> **Pogrubienie** = kluczowe słowa, warto zaakcentować

---

## 1. OTWARCIE — problem (30–45 sek.)

> *(Stój przy robocie, ale jeszcze go nie włączaj)*

„Każdy język niesie ze sobą kulturę — pieśni, poezję, sposób myślenia.
Większość języków ma kraj, który o nie dba.
**Esperanto nie ma żadnego.**

To język stworzony 130 lat temu, żeby połączyć ludzi ponad granicami —
neutralny kulturowo, należący do wszystkich.
Dziś mówi nim około **2 milionów osób** na całym świecie,
ale dostęp do materiałów edukacyjnych jest rozproszony i nierówny.

Nasz znajomy esperantysta — i to jego pomysł był punktem wyjścia —
powiedział nam wprost: *trudno zacząć, bo nie wiadomo skąd wziąć materiały.*

Dlatego zbudowaliśmy robota, który **uczy, rozmawia i przechowuje kulturę esperanto** — w jednym urządzeniu."

---

## 2. DEMO — robot na żywo (60–90 sek.)

> *(Włącz robota — wejdzie w AttractMode automatycznie)*

„Zobaczcie — robot sam wykrywa obecność człowieka i wychodzi mu naprzeciw."

`[DEMO]` *Poczekaj na sekwencję attract — quiz słówkowy lub fragment muzyki*

„W trybie fiszek robot stosuje algorytm **SM-2** — ten sam, który jest w Anki.
Sam oblicza, które słowo pokazać i kiedy, na podstawie historii odpowiedzi."

`[DEMO]` *Wejdź do trybu FLASHCARDS, odpowiedz TAK i NIE na kilka słówek*

„A teraz — rozmowa po esperanto z AI."

`[DEMO]` *Wejdź do trybu CONVERSATION, nagraj jedno zdanie po esperanto lub po polsku*

„Robot rozpoznaje mowę modelem fine-tuned **specjalnie na esperanto**,
wysyła do LLM i odpowiada głosem — w czasie rzeczywistym, dostosowując poziom do rozmówcy."

---

## 3. ROZWIĄZANIE — jak to działa (60 sek.)

`[SLAJD]` *(diagram architektury: SPIKE Prime ↔ BLE ↔ PC)*

„Mamy **dwa kontrolery** połączone przez Bluetooth:
LEGO SPIKE Prime obsługuje czujniki, silnik, LED i przyciski.
Komputer PC przetwarza mowę, zarządza AI i przechowuje archiwum.

Robot ma **cztery tryby**:
— fiszki z powtórkami SM-2,
— poezja esperanto z metadanymi,
— muzyka esperanto,
— i rozmowa z AI na trzech poziomach: A1, B1, C1.

To cyfrowe **archiwum języka** — słownik, poezja i muzyka w jednym miejscu,
dostępne dla każdego bez internetu."

---

## 4. POWIĄZANIE Z TEMATEM WRO (45 sek.)

„Nasz projekt wpisuje się we wszystkie trzy obszary tegorocznego tematu.

**Obszar 1 — ochrona dziedzictwa:**
Digitalizujemy słownictwo i kulturę esperanto — język bez instytucji państwowej, która by o nim dbała.

**Obszar 2 — współtworzenie z AI:**
LLM nie tylko odpowiada — jest **partnerem językowym**,
który dostosowuje się do każdej rozmowy.

**Obszar 3 — doświadczanie kultury:**
Tryb Attract aktywnie zaprasza przechodniów —
robot wychodzi do ludzi, nie czeka aż przyjdą.

Projekt wspiera też **SDG 4** — dobra edukacja dla wszystkich —
i **SDG 11** — ochrona dziedzictwa kulturowego."

---

## 5. ZAMKNIĘCIE (20–30 sek.)

„Esperanto powstało z przekonania, że wspólny język może połączyć ludzi.
Nasz robot kontynuuje tę ideę — uczy, rozmawia, zachowuje.

Dziękujemy."

---

## Spodziewane pytania jury i odpowiedzi

**„Jak robot podejmuje autonomiczne decyzje?"**
> Trzy niezależne warstwy: SM-2 decyduje o kolejności fiszek, adaptacyjna kolejka dobiera muzykę, LLM generuje unikalną odpowiedź na każdą wypowiedź — żadna z tych decyzji nie jest z góry zaplanowana.

**„Skąd pomysł na esperanto?"**
> Od znajomego esperantysty, który wskazał konkretny problem: brak dostępnych, zintegrowanych materiałów edukacyjnych. Projekt jest odpowiedzią na realną potrzebę, nie wymysłem.

**„Dlaczego LEGO SPIKE Prime, a nie np. Raspberry Pi?"**
> SPIKE Prime daje gotowe czujniki, silnik i matrycę LED w jednym. PC obsługuje ciężkie obliczenia (AI, STT). Podział jest celowy — każdy kontroler robi to, co robi najlepiej.

**„Czy robot działa bez internetu?"**
> Fiszki, poezja i muzyka — tak, w pełni offline. Rozmowa z AI wymaga internetu (Groq API). Rozpoznawanie mowy jest lokalne — wav2vec2 działa na komputerze.

**„Co byście zmienili, gdybyście mieli więcej czasu?"**
> Kontekstowe przejście z rozmowy do muzyki/poezji — jeśli AI wykryje temat kulturowy, robot sam zaproponuje odpowiedni fragment. Oraz skrypt do importu słowników — żeby każdy mógł zasilić robota własnym słownikiem.

---

## Podział ról podczas prezentacji

*(dostosuj do siebie)*

| Fragment | Kto mówi | Co robi drugi |
|---|---|---|
| Otwarcie — problem | osoba A | stoi przy robocie |
| Demo | osoba B | obsługuje robota |
| Jak to działa | osoba A | wskazuje slajd |
| Temat WRO + zamknięcie | osoba B | — |
| Pytania jury | oboje | odpowiada ten, kto zna temat |