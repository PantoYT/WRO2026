# Espero-bot — dwukierunkowy protokół BLE (hub ↔ PC)

Stan: **naprawiony i działający w obu kierunkach** (2026-06-12).
Źródła: `pybricks_docs/` (oficjalna dokumentacja Pybricks v4.0) oraz
Pybricks Profile (stałe w `pybricksdev.ble.pybricks`).

## Warstwa transportowa

Pybricks (firmware ≥ 3.3) wystawia **jedną** charakterystykę GATT, która
obsługuje oba kierunki:

| UUID | Rola |
|---|---|
| `c5f50002-8280-46da-89f4-6d8051e4aeef` | command/event — zapis = komenda PC→hub, notyfikacja = zdarzenie hub→PC |
| `c5f50003-8280-46da-89f4-6d8051e4aeef` | hub capabilities — `uint16 LE` na początku = maks. rozmiar zapisu |

Stary serwis Nordic UART (`6e40000x-...`) istnieje tylko w firmware < 3.3;
`computer.py` trzyma go wyłącznie jako fallback.

### PC → hub (komendy)

Zapis do `c5f50002`: pierwszy bajt to kod komendy, reszta to payload.

| Kod | Komenda | Użycie w projekcie |
|---|---|---|
| `0x01` | START_USER_PROGRAM | autostart `hub.py` po połączeniu |
| `0x06` | WRITE_STDIN | **cała komunikacja PC→hub** — payload trafia do `usys.stdin` na hubie |

Wiadomości są wysyłane jako `"<SYGNAŁ>\n"` i dzielone na kawałki o rozmiarze
`max_write_size − 1` (odczytanym z capabilities; domyślnie 19 B).

> **Na czym polegał bug:** kod wysyłał `0x04` (WRITE_USER_RAM) zamiast
> `0x06` (WRITE_STDIN) — dane lądowały w RAM-ie użytkownika, a nie w stdin,
> więc hub nigdy nie widział komend z PC. Dodatkowo sygnały
> `CONV_LISTEN` / `ATTRACT_SPEAK_*` były tylko `print`owane do konsoli PC,
> a nie wysyłane przez BLE.

### Hub → PC (zdarzenia)

Notyfikacja z `c5f50002`: pierwszy bajt to kod zdarzenia.

| Kod | Zdarzenie | Użycie |
|---|---|---|
| `0x00` | STATUS_REPORT | ignorowane |
| `0x01` | WRITE_STDOUT | **cała komunikacja hub→PC** — wszystko, co hub `print`uje |

Linie mogą być pofragmentowane między notyfikacjami — PC skleja je po `\n`.

## Warstwa aplikacyjna — sygnały

### hub → PC

| Sygnał | Znaczenie |
|---|---|
| `READY` | program huba wystartował (PC odpowiada `MODE:<aktualny>`) |
| `YES` / `NO` / `ACTION_HOLD` | przyciski |
| `MODE:<n>` | hub wszedł w tryb n (0–5) |
| `SLEEP` / `WAKE` | usypianie / wybudzenie |
| `ATTRACT_ENTER` / `ATTRACT_LOST` / `ATTRACT_TIMEOUT` / `ATTRACT_EXIT` | tryb attract |
| `MEDIA_PAUSE` / `MEDIA_RESUME` | menu otwarte/zamknięte w trybie mediów |
| `FILTER:<unit>` / `LESSON_FILTER:<unit>` / `LESSON_EXIT` | fiszki / lekcje |
| `DEBUG:RX:<cmd>` | **ACK** — hub potwierdza odbiór każdej komendy z PC |
| `INFO:...` / `WARN:...` | diagnostyka |

### PC → hub (obsługiwane w `handle_pc_signal` w `hub.py`)

| Sygnał | Reakcja huba |
|---|---|
| `MODE:<n>` | wejście w tryb n; budzi z uśpienia; ignorowane echo własnego `MODE:` |
| `CONV_LISTEN` / `CONV_DONE` | ikona mikrofonu podczas nagrywania w konwersacji |
| `ATTRACT_SPEAK_START` / `ATTRACT_SPEAK_DONE` | wstrzymuje licznik „nikogo nie ma" gdy PC mówi |
| `SLEEP` / `WAKE` | usypia / budzi (idempotentne) |

### Kto co wysyła (PC)

- `ModeManager.switch_to()` → `MODE:<n>` (synchronizacja trybu)
- `ConversationMode._listen_and_reply()` → `CONV_LISTEN` przed nagraniem, `CONV_DONE` po
- `AttractMode._run_sequence()` → `ATTRACT_SPEAK_START` / `ATTRACT_SPEAK_DONE`
- `AttractMode._goodbye_then_sleep()` → `SLEEP` po pożegnaniu
- globalna funkcja `hub_send(msg)` — dostępna w całym `computer.py`

## Ochrona przed pętlą echa MODE

Hub po wejściu w tryb emituje `MODE:<n>`; PC w `switch_to()` odsyła `MODE:<n>`
do huba. Żeby nie było ping-ponga:

- **PC**: `switch_to()` wychodzi wcześnie, gdy tryb się nie zmienia,
- **hub**: `MODE:<n>` z `n == current_mode` (poza menu) jest ignorowane.

Skutek uboczny synchronizacji: po starcie hub dostaje `MODE:0` w odpowiedzi
na `READY` i wychodzi z menu prosto do FLASHCARDS (menu: przytrzymaj LEWY).

## Wydajność odbioru na hubie

`poll_serial()` opróżnia **cały** bufor stdin w jednym ticku pętli (50 ms)
i kolejkuje gotowe linie. Wcześniej czytał 1 znak na tick, więc np.
`ATTRACT_SPEAK_START\n` (20 B) docierał ~1 sekundę.

## Jak przetestować

```bash
# automatyczny round-trip (bez torch/pygame, sam bleak):
python tools/ble_link_test.py --auto

# konsola interaktywna:
python tools/ble_link_test.py
> MODE:2          # hub powinien odpowiedzieć DEBUG:RX:MODE:2 i wejść w MUSIC

# w pełnej aplikacji (TUI) — z dowolnego pod-TUI:
[FC]> hub MODE:2
```

Każda komenda przyjęta przez hub wraca jako `DEBUG:RX:<cmd>`
(w TUI wypisywane jako `[hub-ack] ...`) — to żywy dowód, że kierunek
PC→hub działa.
