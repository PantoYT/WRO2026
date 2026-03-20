from pybricks.hubs import PrimeHub
from pybricks.parameters import Button, Direction, Port, Stop
from pybricks.pupdevices import ColorSensor, Motor, UltrasonicSensor
from pybricks.tools import wait
import urandom

# ============================================================
# KONFIGURACJA
# ============================================================

HOLD_TIME_MS   = 800
DEBOUNCE_MS    = 500
SPEAKER_VOLUME = 20

ANIM_TICK_MS   = 50
POEMS_FRAME_MS = 1200
MUSIC_FRAME_MS = 150

NUM_MODES = 5  # FC, POEMS, MUSIC, CONVERSATION, ATTRACT

# --- Sleep / wake ---
INACTIVITY_TIMEOUT_MS = 60_000   # 1 minuta
WAKE_DISTANCE_CM      = 200      # poniżej tej wartości = ktoś jest blisko
ATTRACT_LOST_MS       = 30_000   # ms bez osoby w zasięgu → smutny dźwięk + sen
SCAN_ANGLE_MAX        = 180
SCAN_SPEED            = 300
SCAN_STEP_MS          = 100

# Korekcja offsetu montażu sensora (+= w prawo, -= w lewo)
SCAN_OFFSET_DEG = 15   # <-- dostosuj do fizycznego montażu

# --- Porty zewnętrzne (zmień gdy robot będzie gotowy fizycznie) ---
DISTANCE_PORT = Port.A           # czujnik odległości ultrasoniczny
SCAN_MOTOR_PORT = Port.B         # silnik skanowania

HUB_BUTTONS = [
    (Button.RIGHT, "YES",  "ACTION_HOLD"),
    (Button.LEFT,  "NO",   "MODE"),
]

# ============================================================
# IKONY TRYBÓW  (5×5, row 0 = góra)
# ============================================================

O = False
I = True

FC_ICON = [
    [O, O, O, O, O],
    [I, I, I, I, I],
    [I, I, I, I, I],
    [I, I, I, I, I],
    [O, O, O, O, O],
]

PO_ICON = [
    [O, O, O, O, O],
    [O, O, I, O, O],
    [O, O, O, O, O],
    [O, O, I, O, O],
    [O, I, O, O, O],
]

MU_ICON = [
    [O, O, O, I, O],
    [O, I, O, I, O],
    [I, I, O, I, O],
    [I, I, O, I, I],
    [I, I, I, I, I],
]

# Ikona trybu konwersacji
CV_ICON = [
    [O, I, I, I, O],
    [O, I, I, I, O],
    [O, I, O, I, O],
    [O, I, I, I, O],
    [O, O, I, O, O],
]

# Ikona attract mode — wykrzyknik = zaproszenie
AT_ICON = [
    [O, O, I, O, O],
    [O, O, I, O, O],
    [O, O, I, O, O],
    [O, O, O, O, O],
    [O, O, I, O, O],
]

# Ikona snu — "Zzz"
SLEEP_ICON = [
    [I, I, I, I, O],
    [O, O, O, I, O],
    [O, O, I, O, O],
    [O, I, O, O, O],
    [I, I, I, I, O],
]

# Ikona mikrofonu (słuchanie w trybie CONV)
MIC_ICON = [
    [O, O, I, O, O],
    [O, I, I, I, O],
    [O, I, I, I, O],
    [O, O, I, O, O],
    [O, I, O, I, O],
]

ATTRACT_PULSE_FRAMES = [
    [
        [O, O, O, O, O],
        [O, O, I, O, O],
        [O, I, I, I, O],
        [O, O, I, O, O],
        [O, O, O, O, O],
    ],
    [
        [O, O, I, O, O],
        [O, I, O, I, O],
        [I, O, I, O, I],
        [O, I, O, I, O],
        [O, O, I, O, O],
    ],
    [
        [I, O, I, O, I],
        [O, I, I, I, O],
        [I, I, I, I, I],
        [O, I, I, I, O],
        [I, O, I, O, I],
    ],
    [
        [O, O, I, O, O],
        [O, I, O, I, O],
        [I, O, I, O, I],
        [O, I, O, I, O],
        [O, O, I, O, O],
    ],
]

MODE_ICONS = [FC_ICON, PO_ICON, MU_ICON, CV_ICON, AT_ICON]
MODE_NAMES = ["FLASHCARDS", "POEMS", "MUSIC", "CONVERSATION", "ATTRACT"]

MODE_SOUNDS = [
    [(523, 80), (659, 120)],
    [(440, 60), (440, 60), (554, 150)],
    [(330, 50), (415, 50), (523, 50), (659, 100)],
    [(523, 60), (587, 60), (659, 60), (784, 120)],
    [(600, 60), (700, 60), (800, 60), (900, 80), (1000, 120)],  # attract = wznoszące
]

SLEEP_SOUND   = [(300, 100), (250, 150), (200, 200)]
WAKE_SOUND    = [(400, 80),  (500, 80),  (600, 80),  (700, 120)]
ATTRACT_SAD   = [(400, 100), (320, 150), (260, 200), (220, 300)]


# ============================================================
# POEMS — ramki znaków interpunkcyjnych
# ============================================================

POEMS_FRAMES = [
    [[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,I,O,O]],
    [[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,I,O,O],[O,I,O,O,O]],
    [[O,O,O,O,O],[O,O,I,O,O],[O,O,O,O,O],[O,O,I,O,O],[O,I,O,O,O]],
    [[O,O,O,O,O],[O,O,I,O,O],[O,O,O,O,O],[O,O,I,O,O],[O,O,O,O,O]],
    [[O,O,I,O,O],[O,O,I,O,O],[O,O,I,O,O],[O,O,O,O,O],[O,O,I,O,O]],
    [[O,I,I,I,O],[O,O,O,I,O],[O,O,I,O,O],[O,O,O,O,O],[O,O,I,O,O]],
    [[O,I,O,I,O],[O,I,O,I,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O]],
    [[O,O,I,O,O],[O,O,I,O,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O]],
    [[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O],[I,O,I,O,I]],
    [[O,O,O,O,O],[O,O,O,O,O],[O,I,I,I,O],[O,O,O,O,O],[O,O,O,O,O]],
]

# ============================================================
# INICJALIZACJA
# ============================================================

hub = PrimeHub()
hub.speaker.volume(SPEAKER_VOLUME)

# Podłącz sensory gdy fizyczny robot będzie gotowy:
try:
    _distance = UltrasonicSensor(DISTANCE_PORT)
    _has_distance = True
except Exception:
    _has_distance = False
    print("distance sensor not found on port A — sleep/wake disabled")

try:
    _scan_motor = Motor(SCAN_MOTOR_PORT, Direction.CLOCKWISE)
    _scan_motor.reset_angle(0)
    # Jedź fizycznie do 0 stopni (silnik wie gdzie jest dzięki encoderowi)
    _scan_motor.run_target(SCAN_SPEED, 0, wait=True)
    _has_motor = True
except Exception:
    _has_motor = False
    print("scan motor not found on port B — scanning disabled")

# ============================================================
# STAN
# ============================================================

current_mode    = 0
anim_counter    = 0
poems_frame     = 0
music_heights   = [urandom.randint(1, 5) for _ in range(5)]
in_menu         = False
menu_selection  = 0
sleeping        = False
last_activity_ms = 0   # ustawiany przez poke_activity()
conv_listening  = False  # animacja mikrofonu w trybie CONV

# --- Attract state ---
in_attract          = False
attract_frame       = 0
attract_anim_ms     = 0
attract_lost_ms     = 0
attract_speaking    = False   # True gdy PC gra sekwencję — nie śpij w połowie
ATTRACT_ANIM_FRAME_MS = 400

# ============================================================
# ACTIVITY
# ============================================================

def poke_activity():
    global last_activity_ms
    last_activity_ms = _elapsed_ms()

def _elapsed_ms():
    """Pseudo-zegar na podstawie liczby ticków."""
    return _tick_counter * ANIM_TICK_MS

_tick_counter = 0

def _inc_tick():
    global _tick_counter
    _tick_counter += 1

# ============================================================
# RYSOWANIE
# ============================================================

def draw_icon(icon):
    hub.display.off()
    for r in range(5):
        for c in range(5):
            if icon[r][c]:
                hub.display.pixel(r, c, 100)

def draw_poems():
    hub.display.off()
    frame = POEMS_FRAMES[poems_frame % len(POEMS_FRAMES)]
    for r in range(5):
        for c in range(5):
            if frame[r][c]:
                hub.display.pixel(r, c, 100)

def draw_music():
    hub.display.off()
    for col in range(5):
        h = music_heights[col]
        for row in range(5 - h, 5):
            hub.display.pixel(row, col, 100)

def draw_conv_idle():
    """Ikona trybu konwersacji — oczekuje na przycisk."""
    draw_icon(CV_ICON)

def draw_conv_listening():
    """Animacja mikrofonu — pulsuje gdy nagrywa."""
    draw_icon(MIC_ICON)

def draw_menu(sel):
    hub.display.off()
    icon = MODE_ICONS[sel % NUM_MODES]
    for r in range(5):
        for c in range(5):
            if icon[r][c]:
                hub.display.pixel(r, c, 100)

def draw_sleep_animation():
    """Powoli pulsujące Zzz."""
    draw_icon(SLEEP_ICON)

def draw_attract_frame():
    draw_icon(ATTRACT_PULSE_FRAMES[attract_frame % len(ATTRACT_PULSE_FRAMES)])

def play_attract_sad():
    for freq, dur in ATTRACT_SAD:
        hub.speaker.beep(frequency=freq, duration=dur)
        wait(20)

def play_mode_sound(mode_idx):
    for freq, dur in MODE_SOUNDS[mode_idx]:
        hub.speaker.beep(frequency=freq, duration=dur)
        wait(20)

def play_sleep_sound():
    for freq, dur in SLEEP_SOUND:
        hub.speaker.beep(frequency=freq, duration=dur)
        wait(30)

def play_wake_sound():
    for freq, dur in WAKE_SOUND:
        hub.speaker.beep(frequency=freq, duration=dur)
        wait(20)

# ============================================================
# SLEEP / WAKE
# ============================================================

def _read_distance_cm():
    """Odczytuje dystans z czujnika. Zwraca None gdy brak sensora lub błąd."""
    if not _has_distance:
        return None
    try:
        d = _distance.distance()
        return d / 10  # mm → cm
    except Exception:
        return None

# Wahadlo: 0 -> 90 -> -90 -> 90 -> -90 ...
# Nigdy nie przekracza ±90, kable bezpieczne
_SCAN_LOGICAL = [45, -45]   # logiczne cele ±45° (razem 90° zasięgu)
_scan_idx = 0

def _scan_step():
    """Wahadlo z korekcja offsetu montazu sensora."""
    global _scan_idx
    if not _has_motor:
        return
    try:
        physical_target = _SCAN_LOGICAL[_scan_idx] + SCAN_OFFSET_DEG
        angle = _scan_motor.angle()
        if abs(angle - physical_target) <= 8:
            _scan_idx = 1 - _scan_idx
            physical_target = _SCAN_LOGICAL[_scan_idx] + SCAN_OFFSET_DEG
        _scan_motor.run_target(SCAN_SPEED, physical_target, wait=False)
    except Exception:
        pass

def _motor_home():
    """Wraca do pozycji startowej (0 = prosto przed siebie)."""
    if not _has_motor:
        return
    try:
        _scan_motor.run_target(SCAN_SPEED, 0, wait=True)
    except Exception:
        pass

def enter_sleep():
    global sleeping, _scan_idx, in_attract
    sleeping   = True
    in_attract = False
    _scan_idx  = 0
    draw_sleep_animation()
    play_sleep_sound()
    print("SLEEP")

def exit_sleep():
    global sleeping
    sleeping = False
    play_wake_sound()
    print("WAKE")
    _motor_home()
    enter_attract()   # zawsze attract po przebudzeniu

def check_wake():
    """Skanuje silnikiem i sprawdza dystans. Po wykryciu budzi robota."""
    _scan_step()
    dist = _read_distance_cm()
    if dist is not None and dist < WAKE_DISTANCE_CM:
        exit_sleep()   # exit_sleep sam wywoluje _motor_home()

# ============================================================
# ATTRACT MODE
# ============================================================

def enter_attract():
    global in_attract, attract_frame, attract_anim_ms, attract_lost_ms
    in_attract       = True
    attract_frame    = 0
    attract_anim_ms  = 0
    attract_lost_ms  = 0
    draw_attract_frame()
    play_mode_sound(4)
    print("MODE:4")
    print("ATTRACT_ENTER")
    poke_activity()

def tick_attract():
    global attract_frame, attract_anim_ms, attract_lost_ms, in_attract

    attract_anim_ms += ANIM_TICK_MS
    if attract_anim_ms >= ATTRACT_ANIM_FRAME_MS:
        attract_anim_ms = 0
        attract_frame   = (attract_frame + 1) % len(ATTRACT_PULSE_FRAMES)
        draw_attract_frame()

    dist = _read_distance_cm()
    if dist is not None and dist < WAKE_DISTANCE_CM:
        attract_lost_ms = 0
    else:
        # Nie licz czasu gdy PC gra sekwencję (attract_speaking = True)
        if not attract_speaking:
            attract_lost_ms += ANIM_TICK_MS
            if attract_lost_ms >= ATTRACT_LOST_MS:
                attract_lost_ms = 0
                in_attract      = False
                print("ATTRACT_LOST")
                # Nie przerywaj — PC sam skończy sekwencję i wyśle ATTRACT_DONE
                # Hub gra smutny dźwięk dopiero gdy dostanie ATTRACT_SAD_PLAY
                print("ATTRACT_TIMEOUT")  # PC zdecyduje kiedy zagrać smutny dźwięk

def exit_attract_to_menu():
    global in_attract
    in_attract = False
    print("ATTRACT_EXIT")
    open_menu()

# ============================================================
# ANIMACJA
# ============================================================

def update_anim():
    global anim_counter, poems_frame, music_heights
    if in_menu or sleeping or in_attract:
        return
    if current_mode == 0:
        return
    if current_mode == 3:
        # CONV — animacja zależy od stanu (idle / listening)
        # conv_listening jest ustawiany przez sygnał CONV_LISTEN z PC
        return
    anim_counter += ANIM_TICK_MS
    if current_mode == 1 and anim_counter >= POEMS_FRAME_MS:
        anim_counter = 0
        poems_frame  = (poems_frame + 1) % len(POEMS_FRAMES)
        draw_poems()
    elif current_mode == 2 and anim_counter >= MUSIC_FRAME_MS:
        anim_counter  = 0
        music_heights = [urandom.randint(1, 5) for _ in range(5)]
        draw_music()

# ============================================================
# WEJŚCIE W TRYB
# ============================================================

def enter_mode(mode_idx):
    global current_mode, anim_counter, poems_frame, music_heights, conv_listening, in_attract
    current_mode   = mode_idx % NUM_MODES
    anim_counter   = 0
    conv_listening = False
    in_attract     = False

    if current_mode == 0:
        draw_icon(FC_ICON)
    elif current_mode == 1:
        poems_frame = 0
        draw_poems()
    elif current_mode == 2:
        music_heights = [urandom.randint(1, 5) for _ in range(5)]
        draw_music()
    elif current_mode == 3:
        draw_conv_idle()
    elif current_mode == 4:
        enter_attract()
        return

    play_mode_sound(current_mode)
    print(f"MODE:{current_mode}")
    poke_activity()

# ============================================================
# MENU TRYBU
# ============================================================

def open_menu():
    global in_menu, menu_selection
    in_menu        = True
    menu_selection = current_mode
    draw_menu(menu_selection)
    # Sygnalizuj PC żeby spauzował odtwarzanie
    if current_mode in (1, 2):
        print("MEDIA_PAUSE")
    hub.speaker.beep(frequency=600, duration=100)
    wait(120)
    hub.speaker.beep(frequency=800, duration=100)

def menu_cycle():
    global menu_selection
    menu_selection = (menu_selection + 1) % NUM_MODES
    draw_menu(menu_selection)
    hub.speaker.beep(frequency=700, duration=80)

def menu_confirm():
    global in_menu
    in_menu = False
    # Jeśli wracamy do trybu mediów który był pauzowany — wznów
    if menu_selection in (1, 2):
        print("MEDIA_RESUME")
    enter_mode(menu_selection)

# ============================================================
# HELPERS PRZYCISKÓW
# ============================================================

def is_held(button, ms):
    elapsed = 0
    while button in hub.buttons.pressed():
        wait(ANIM_TICK_MS)
        elapsed += ANIM_TICK_MS
        update_anim()
        if elapsed >= ms:
            return True
    return False

def wait_release_all():
    while hub.buttons.pressed():
        wait(ANIM_TICK_MS)
        update_anim()

# ============================================================
# OBSŁUGA SYGNAŁÓW Z PC
# ============================================================

def handle_pc_signal(line):
    """Obsługuje dodatkowe sygnały przychodzące z komputera przez stdout echo.
    
    Uwaga: pybricksdev echo'uje print() z huba, ale hub nie czyta stdin.
    Sygnały z PC → hub realizujemy przez print() z PC odczytywany na konsoli
    przez operatora LUB przez osobny mechanizm BLE characteristic (przyszłość).
    
    Na razie: hub wysyła sygnały → PC reaguje.
    PC nie wysyła do huba bezpośrednio w tej architekturze.
    CONV_LISTEN jest emitowany przez PC na stdout — nie przez huba.
    """
    global conv_listening
    if line == "CONV_LISTEN":
        conv_listening = True
        draw_conv_listening()
    elif line == "CONV_DONE":
        conv_listening = False
        if current_mode == 3:
            draw_conv_idle()

# ============================================================
# GŁÓWNA PĘTLA
# ============================================================

open_menu()
poke_activity()
print("READY")

scan_tick = 0

while True:
    _inc_tick()

    if sleeping:
        scan_tick += ANIM_TICK_MS
        if scan_tick >= SCAN_STEP_MS:
            scan_tick = 0
            check_wake()
        if hub.buttons.pressed():
            poke_activity()
            exit_sleep()
        wait(ANIM_TICK_MS)
        continue

    if in_attract:
        if hub.buttons.pressed():
            poke_activity()
            wait_release_all()
            wait(DEBOUNCE_MS)
            exit_attract_to_menu()
        else:
            tick_attract()
        wait(ANIM_TICK_MS)
        continue

    if _elapsed_ms() - last_activity_ms >= INACTIVITY_TIMEOUT_MS:
        enter_sleep()
        wait(ANIM_TICK_MS)
        continue

    pressed = hub.buttons.pressed()

    if in_menu:
        if Button.RIGHT in pressed:
            poke_activity()
            wait_release_all()
            wait(DEBOUNCE_MS)
            menu_cycle()
        elif Button.LEFT in pressed:
            poke_activity()
            wait_release_all()
            wait(DEBOUNCE_MS)
            menu_confirm()

    else:
        for (btn, short_action, long_action) in HUB_BUTTONS:
            if btn in pressed:
                poke_activity()
                if is_held(btn, HOLD_TIME_MS):
                    hub.speaker.beep(
                        frequency=1000 if btn == Button.RIGHT else 500,
                        duration=200
                    )
                    wait_release_all()
                    wait(DEBOUNCE_MS)
                    if long_action == "MODE":
                        open_menu()
                    else:
                        print(long_action)
                else:
                    hub.speaker.beep(
                        frequency=880 if btn == Button.RIGHT else 440,
                        duration=100
                    )
                    wait_release_all()
                    wait(DEBOUNCE_MS)
                    print(short_action)
                break

    update_anim()
    wait(ANIM_TICK_MS)