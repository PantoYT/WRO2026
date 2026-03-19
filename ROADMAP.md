# Roadmap — WRO2026 Esperanto Flashcard Robot

## Planowane: Tryb konwersacji AI

Nowy tryb (Mode 3) — rozmowa po esperanto z LLM jako partnerem językowym.

```
[Mikrofon]  →  Whisper STT  →  LLM (Ollama / API)  →  gTTS  →  głośnik
                                     ↑
                          system prompt: poziom trudności,
                          rola: natywny użytkownik esperanto
```

### Poziomy trudności (wybierane w menu huba)

| Poziom | Opis |
|--------|------|
| A1 | krótkie zdania, podstawowe słownictwo z wordlist.json |
| B1 | swobodna rozmowa, korekta błędów |
| C1 | natywne tempo, idiomy, kultura |

- Ollama lokalnie (RTX 3060) = fallback offline na konkurs, brak zależności od internetu
- API (Gemini / GPT-4o) jako opcja gdy dostępny hotspot
- Zakres ograniczony do dialogów edukacyjnych — AI uczy się poziomu użytkownika i dostosowuje język

---

## Planowane: Fizyczna interakcja / "robotyczność"

WRO wymaga fizycznego systemu z sensorami — samo PC + przyciski to za mało.

- **Kamera laptopa + detekcja obecności** — gdy ktoś podejdzie, robot się "budzi" (wychodzi ze snu, odpala menu). Zamiast dedykowanego sensora używamy kamery która już jest.
- **Tryb snu** — po X sekundach bezczynności robot przechodzi w tryb uśpienia (animacja LED, wyciszenie). Proaktywne zachowanie bez przycisku.

---

## Planowane: Proaktywna autonomia

Teraz robot tylko reaguje na przyciski. Upgrade:

- Brak aktywności → auto-start muzyki / powrót do fiszek
- Dużo błędów w fiszkach → robot sam proponuje powrót do trudnych słów
- (opcjonalnie) pora dnia → zmiana trybu

---

## Planowane: Prezentacja WRO

- [ ] Slajdy (problem → rozwiązanie → demo → wpływ kulturowy → SDG 4 + 11)
- [ ] Demo na żywo: fiszki SM-2, muzyka/poezja z TTS, tryb rozmowy AI
- [ ] Uzasadnienie wyboru esperanto jako dziedzictwa kulturowego

---

## Uwagi techniczne

- Agent AI jako osobny proces — awaria nie zawiesza reszty robota
- Przyciski fizyczne zawsze działają niezależnie od stanu AI (redundancja)
- Kamera laptopa zamiast dedykowanego sensora — prostsze, mniej sprzętu