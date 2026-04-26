from pybricks.hubs import PrimeHub
from pybricks.parameters import Button, Direction, Port, Stop
from pybricks.pupdevices import ColorSensor, Motor, UltrasonicSensor, ForceSensor
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

NUM_MODES = 6  # FC, POEMS, MUSIC, CONVERSATION, ATTRACT, A0_LESSON

# --- Sleep / wake ---
INACTIVITY_TIMEOUT_MS = 60_000
WAKE_DISTANCE_CM      = 200
ATTRACT_LOST_MS       = 30_000
SCAN_ANGLE_MAX        = 180
SCAN_SPEED            = 300
SCAN_STEP_MS          = 100

# Korekcja offsetu montażu sensora (+= w prawo, -= w lewo)
SCAN_OFFSET_DEG = 15

# --- Porty ---
DISTANCE_PORT   = Port.A
SCAN_MOTOR_PORT = Port.B
BTN_LEFT_PORT   = Port.E   # Zewnętrzny przycisk LEWY  — NO / MODE
BTN_RIGHT_PORT  = Port.F   # Zewnętrzny przycisk PRAWY — YES / ACTION_HOLD

# Próg nacisku ForceSensor [N]; ~3 = wyraźne naciśnięcie, nie przypadkowe
BTN_FORCE_THRESHOLD = 1

# ============================================================
# IKONY TRYBÓW
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

CV_ICON = [
    [O, I, I, I, O],
    [O, I, I, I, O],
    [O, I, O, I, O],
    [O, I, I, I, O],
    [O, O, I, O, O],
]

AT_ICON = [
    [O, O, I, O, O],
    [O, O, I, O, O],
    [O, O, I, O, O],
    [O, O, O, O, O],
    [O, O, I, O, O],
]

SLEEP_ICON = [
    [I, I, I, I, O],
    [O, O, O, I, O],
    [O, O, I, O, O],
    [O, I, O, O, O],
    [I, I, I, I, O],
]

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

# Ikona trybu A0 — litera A (lekcja / nauka)
A0_ICON = [
    [O, O, I, O, O],
    [O, I, O, I, O],
    [O, I, I, I, O],
    [O, I, O, I, O],
    [O, I, O, I, O],
]

MODE_ICONS = [FC_ICON, PO_ICON, MU_ICON, CV_ICON, AT_ICON, A0_ICON]
MODE_NAMES = ["FLASHCARDS", "POEMS", "MUSIC", "CONVERSATION", "ATTRACT", "A0_LESSON"]

MODE_SOUNDS = [
    [(523, 80), (659, 120)],
    [(440, 60), (440, 60), (554, 150)],
    [(330, 50), (415, 50), (523, 50), (659, 100)],
    [(523, 60), (587, 60), (659, 60), (784, 120)],
    [(600, 60), (700, 60), (800, 60), (900, 80), (1000, 120)],
    [(523, 60), (659, 60), (784, 60), (659, 60), (523, 120)],  # A0 = melodyjka w górę i dół
]

SLEEP_SOUND   = [(300, 100), (250, 150), (200, 200)]
WAKE_SOUND    = [(400, 80),  (500, 80),  (600, 80),  (700, 120)]
ATTRACT_SAD   = [(400, 100), (320, 150), (260, 200), (220, 300)]

# ============================================================
# POEMS — ramki
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

try:
    _distance = UltrasonicSensor(DISTANCE_PORT)
    _has_distance = True
except Exception:
    _has_distance = False
    print("distance sensor not found on port A — sleep/wake disabled")

# Zewnętrzne przyciski siłowe (ForceSensor) na portach E i F
try:
    _btn_left  = ForceSensor(BTN_LEFT_PORT)   # Port E — NO / MODE
    _btn_right = ForceSensor(BTN_RIGHT_PORT)  # Port F — YES / ACTION_HOLD
    _has_force_btns = True
    print("Force buttons on E/F ready")
except Exception:
    _btn_left = _btn_right = None
    _has_force_btns = False
    print("Force buttons not found on E/F — falling back to hub buttons")

try:
    _scan_motor = Motor(SCAN_MOTOR_PORT, Direction.CLOCKWISE)
    _scan_motor.reset_angle(0)
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
last_activity_ms = 0
conv_listening  = False

in_attract          = False
attract_frame       = 0
attract_anim_ms     = 0
attract_lost_ms     = 0
attract_speaking    = False
ATTRACT_ANIM_FRAME_MS = 400

# ============================================================
# ACTIVITY
# ============================================================

def poke_activity():
    global last_activity_ms
    last_activity_ms = _elapsed_ms()

def _elapsed_ms():
    return _tick_counter * ANIM_TICK_MS

_tick_counter = 0

def _inc_tick():
    global _tick_counter
    _tick_counter += 1

# ============================================================
# ROTACJA MATRYCY — 90° zgodnie z ruchem zegara
# Hub jest zamontowany obrócony — ta funkcja koryguje wyświetlanie.
# Wzór CW 90°: new[r][c] = old[4-c][r]
# ============================================================

def rotate_cw(icon):
    """Obraca wzór 5x5 o 90° zgodnie z ruchem zegara."""
    return [[icon[4 - c][r] for c in range(5)] for r in range(5)]

# ============================================================
# RYSOWANIE
# ============================================================

def draw_icon(icon):
    hub.display.off()
    rotated = rotate_cw(icon)
    for r in range(5):
        for c in range(5):
            if rotated[r][c]:
                hub.display.pixel(r, c, 100)

def draw_poems():
    hub.display.off()
    frame   = POEMS_FRAMES[poems_frame % len(POEMS_FRAMES)]
    rotated = rotate_cw(frame)
    for r in range(5):
        for c in range(5):
            if rotated[r][c]:
                hub.display.pixel(r, c, 100)

def draw_music():
    """Słupki equalizer — dla muzyki nie robimy rotacji bo to dynamiczny pattern.
    Jeśli po zamontowaniu słupki są poziome zamiast pionowych zmień na rotate_cw."""
    hub.display.off()
    for col in range(5):
        h = music_heights[col]
        for row in range(5 - h, 5):
            hub.display.pixel(row, col, 100)

def draw_conv_idle():
    draw_icon(CV_ICON)

def draw_conv_listening():
    draw_icon(MIC_ICON)

def draw_menu(sel):
    hub.display.off()
    icon = MODE_ICONS[sel % NUM_MODES]
    for r in range(5):
        for c in range(5):
            if icon[r][c]:
                hub.display.pixel(r, c, 100)

def draw_sleep_animation():
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
# H3: filtr ostatniej poprawnej wartości czujnika odległości
# ============================================================

_last_distance = None   # H3: cache ostatniej dobrej wartości

def _read_distance_cm():
    """Odczytuje dystans z czujnika.
    H3: jeśli odczyt zwróci None, używa ostatniej poprawnej wartości.
    Eliminuje fałszywe 'nikogo nie ma' gdy sensor chwilowo zawiedzie.
    """
    global _last_distance
    if not _has_distance:
        return None
    try:
        d = _distance.distance()
        if d is not None:
            _last_distance = d / 10  # mm → cm
    except Exception:
        pass
    return _last_distance

# H2: debounce celu silnika skanowania — nie restart gdy cel się nie zmienił
_SCAN_LOGICAL = [45, -45]
_scan_idx     = 0
_scan_target  = None   # H2: poprzedni cel fizyczny

def _scan_step():
    """Wahadło z korekcją offsetu montażu sensora.
    H2: run_target() wywoływane tylko przy zmianie celu — eliminuje szarpanie.
    """
    global _scan_idx, _scan_target
    if not _has_motor:
        return
    try:
        physical_target = _SCAN_LOGICAL[_scan_idx] + SCAN_OFFSET_DEG
        angle = _scan_motor.angle()
        if abs(angle - physical_target) <= 8:
            _scan_idx = 1 - _scan_idx
            physical_target = _SCAN_LOGICAL[_scan_idx] + SCAN_OFFSET_DEG
        if _scan_target != physical_target:   # H2: tylko gdy cel się zmienia
            _scan_target = physical_target
            _scan_motor.run_target(SCAN_SPEED, physical_target, wait=False)
    except Exception:
        pass

def _motor_home():
    """Wraca do pozycji startowej (0 = prosto przed siebie)."""
    global _scan_target
    if not _has_motor:
        return
    try:
        _scan_motor.run_target(SCAN_SPEED, 0, wait=True)
        _scan_target = 0   # H2: sync cache
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
    enter_attract()

def check_wake():
    _scan_step()
    dist = _read_distance_cm()
    if dist is not None and dist < WAKE_DISTANCE_CM:
        exit_sleep()

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
        if not attract_speaking:
            attract_lost_ms += ANIM_TICK_MS
            if attract_lost_ms >= ATTRACT_LOST_MS:
                attract_lost_ms = 0
                in_attract      = False
                print("ATTRACT_LOST")
                print("ATTRACT_TIMEOUT")

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
    elif current_mode == 5:
        draw_icon(A0_ICON)

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
    if menu_selection in (1, 2):
        print("MEDIA_RESUME")
    enter_mode(menu_selection)

# ============================================================
# HELPERS PRZYCISKÓW
# ============================================================

# Stany przycisków force z poprzedniego ticku — do debounce
_prev_left  = False
_prev_right = False

def _read_buttons():
    """Czyta stan przycisków E/F (ForceSensor) albo wbudowanych guzików huba.
    Zwraca (left_pressed, right_pressed) jako bool.
    Próg BTN_FORCE_THRESHOLD [N] eliminuje przypadkowe dotknięcia.
    """
    if _has_force_btns:
        try:
            left  = _btn_left.pressed(BTN_FORCE_THRESHOLD)
            right = _btn_right.pressed(BTN_FORCE_THRESHOLD)
            return left, right
        except Exception:
            pass
    # fallback — wbudowane guziki
    pressed = hub.buttons.pressed()
    return (Button.LEFT in pressed), (Button.RIGHT in pressed)

def is_held(button, ms):
    """Czeka czy dany przycisk jest trzymany przez ms milisekund.
    button: 'left' lub 'right' (string) — nie Button enum.
    """
    elapsed = 0
    while True:
        left, right = _read_buttons()
        still_held = (left if button == 'left' else right)
        if not still_held:
            return False
        wait(ANIM_TICK_MS)
        elapsed += ANIM_TICK_MS
        update_anim()
        if elapsed >= ms:
            return True

def wait_release_all():
    while True:
        left, right = _read_buttons()
        if not left and not right:
            break
        wait(ANIM_TICK_MS)
        update_anim()

# ============================================================
# OBSŁUGA SYGNAŁÓW Z PC
# ============================================================

def handle_pc_signal(line):
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
        _sl, _sr = _read_buttons()
        if _sl or _sr or hub.buttons.pressed():
            poke_activity()
            exit_sleep()
        wait(ANIM_TICK_MS)
        continue

    if in_attract:
        _al, _ar = _read_buttons()
        if _al or _ar or hub.buttons.pressed():
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

    left_now, right_now = _read_buttons()

    if in_menu:
        # W menu: RIGHT = cykl, LEFT = potwierdź.
        # Hold nie jest potrzebny w menu — krótkie naciśnięcie wystarczy.
        if right_now:
            poke_activity()
            wait_release_all()
            wait(DEBOUNCE_MS)
            menu_cycle()
        elif left_now:
            poke_activity()
            wait_release_all()
            wait(DEBOUNCE_MS)
            menu_confirm()

    else:
        # Poza menu: krótkie = akcja, długie (hold) = akcja alternatywna.
        # is_held() liczy czas OD momentu wykrycia naciśnięcia.
        # Ważne: is_held kontynuuje czytać _read_buttons() w pętli — działa na E/F i na hubie.
        if right_now:
            poke_activity()
            if is_held('right', HOLD_TIME_MS):
                # Długie RIGHT — powtórz definicję / przeczytaj metadata / zmień poziom
                hub.speaker.beep(frequency=1000, duration=200)
                wait_release_all()
                wait(DEBOUNCE_MS)
                print("ACTION_HOLD")
            else:
                # Krótkie RIGHT — YES / następny / push-to-talk
                hub.speaker.beep(frequency=880, duration=100)
                wait_release_all()
                wait(DEBOUNCE_MS)
                print("YES")
        elif left_now:
            poke_activity()
            if is_held('left', HOLD_TIME_MS):
                # Długie LEFT — otwórz menu trybów
                hub.speaker.beep(frequency=500, duration=200)
                wait_release_all()
                wait(DEBOUNCE_MS)
                open_menu()
            else:
                # Krótkie LEFT — NO / poprzedni / anuluj
                hub.speaker.beep(frequency=440, duration=100)
                wait_release_all()
                wait(DEBOUNCE_MS)
                print("NO")

    update_anim()
    wait(ANIM_TICK_MS)