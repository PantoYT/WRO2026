from pybricks.hubs import PrimeHub
from pybricks.parameters import Button, Direction, Port, Stop
from pybricks.pupdevices import Motor, UltrasonicSensor, ForceSensor
from pybricks.tools import wait
import urandom
from usys import stdin, stdout
from uselect import poll as uselect_poll

# ============================================================
# CONFIG
# ============================================================

HOLD_TIME_MS   = 1500
DEBOUNCE_MS    = 500
SPEAKER_VOLUME = 20

ANIM_TICK_MS   = 50
POEMS_FRAME_MS = 1200
MUSIC_FRAME_MS = 150

NUM_MODES = 6  # FC, POEMS, MUSIC, CONVERSATION, ATTRACT, A0_LESSON

# --- Sleep / wake ---
INACTIVITY_TIMEOUT_MS = 180_000
WAKE_DISTANCE_CM      = 200
ATTRACT_LOST_MS       = 30_000
SCAN_SPEED            = 200          # slower = smoother sweep
SCAN_STEP_MS          = 100

# Sensor mount offset correction (+= right, -= left)
SCAN_OFFSET_DEG = 15

# --- Ports ---
DISTANCE_PORT   = Port.A
SCAN_MOTOR_PORT = Port.B
FLAG_MOTOR_PORT = Port.D
BTN_LEFT_PORT   = Port.E   # External LEFT  button — NO / MENU
BTN_RIGHT_PORT  = Port.F   # External RIGHT button — YES / ACTION_HOLD

# ForceSensor press threshold [N]; ~1 = clear press, not accidental
BTN_FORCE_THRESHOLD = 1

# --- Flag ---
FLAG_SPEED = 100  # degrees/s

# ============================================================
# MODE ICONS — 5×5 pixel letters (top-row first, left-col first)
# ============================================================

O = False
I = True

# F — Flashcards
FC_ICON = [
    [O, O, O, O, O],
    [O, O, O, O, O],
    [I, I, I, I, I],
    [O, O, I, O, I],
    [O, O, O, O, I],
]

# P — Poems
PO_ICON = [
    [O, O, O, O, O],
    [O, O, O, O, O],
    [I, I, I, I, I],
    [O, O, I, O, I],
    [O, O, O, I, O],
]

# M — Music
MU_ICON = [
    [I, I, I, I, I],
    [O, O, O, I, O],
    [O, O, I, O, O],
    [O, O, O, I, O],
    [I, I, I, I, I],
]

# K — Conversation (Konversation)
CV_ICON = [
    [O, O, O, O, O],
    [I, I, I, I, I],
    [O, O, I, O, O],
    [O, I, O, I, O],
    [I, O, O, O, I],
]

# ! — Attract
AT_ICON = [
    [O, O, O, O, O],
    [O, O, O, O, O],
    [I, O, I, I, I],
    [O, O, O, O, O],
    [O, O, O, O, O],
]

# L — A0 Lesson
A0_ICON = [
    [O, O, O, O, O],
    [I, I, I, I, I],
    [I, O, O, O, I],
    [I, I, I, I, I],
    [O, O, O, O, O],
]

SLEEP_ICON = [
    [I, O, O, O, I],
    [I, I, O, O, I],
    [I, O, I, O, I],
    [I, O, O, I, I],
    [I, O, O, O, I],
]

MIC_ICON = [
    [O, O, O, O, O],
    [I, O, I, I, O],
    [O, I, I, I, I],
    [I, O, I, I, O],
    [O, O, O, O, O],
]

ATTRACT_PULSE_FRAMES = [
    [[O,O,O,O,O],[O,O,I,O,O],[O,I,I,I,O],[O,O,I,O,O],[O,O,O,O,O]],
    [[O,O,I,O,O],[O,I,O,I,O],[I,O,I,O,I],[O,I,O,I,O],[O,O,I,O,O]],
    [[I,O,I,O,I],[O,I,I,I,O],[I,I,I,I,I],[O,I,I,I,O],[I,O,I,O,I]],
    [[O,O,I,O,O],[O,I,O,I,O],[I,O,I,O,I],[O,I,O,I,O],[O,O,I,O,O]],
]

MODE_ICONS = [FC_ICON, PO_ICON, MU_ICON, CV_ICON, AT_ICON, A0_ICON]
MODE_NAMES = ["FLASHCARDS", "POEMS", "MUSIC", "CONVERSATION", "ATTRACT", "A0_LESSON"]

MODE_SOUNDS = [
    [(523, 80),  (659, 120)],
    [(440, 60),  (440, 60),  (554, 150)],
    [(330, 50),  (415, 50),  (523, 50),  (659, 100)],
    [(523, 60),  (587, 60),  (659, 60),  (784, 120)],
    [(600, 60),  (700, 60),  (800, 60),  (900, 80),  (1000, 120)],
    [(523, 60),  (659, 60),  (784, 60),  (659, 60),  (523, 120)],
]

SLEEP_SOUND = [(300, 100), (250, 150), (200, 200)]
WAKE_SOUND  = [(400, 80),  (500, 80),  (600, 80),  (700, 120)]
ATTRACT_SAD = [(400, 100), (320, 150), (260, 200), (220, 300)]

# ============================================================
# POEMS — animation frames
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

def rotate_right(icon):
    """Rotate 5×5 icon 90 degrees clockwise."""
    return [[icon[4 - c][r] for c in range(5)] for r in range(5)]

_serial_buf = ""
_keyboard = uselect_poll()
_keyboard.register(stdin)

# ============================================================
# HARDWARE INIT
# ============================================================

hub = PrimeHub()
hub.speaker.volume(SPEAKER_VOLUME)

try:
    _distance    = UltrasonicSensor(DISTANCE_PORT)
    _has_distance = True
except Exception:
    _has_distance = False
    print("WARN:NO_DISTANCE_SENSOR")

try:
    _btn_left        = ForceSensor(BTN_LEFT_PORT)
    _btn_right       = ForceSensor(BTN_RIGHT_PORT)
    _has_force_btns  = True
    print("INFO:FORCE_BTNS_OK")
except Exception:
    _btn_left = _btn_right = None
    _has_force_btns        = False
    print("WARN:NO_FORCE_BTNS")

try:
    _scan_motor = Motor(SCAN_MOTOR_PORT, Direction.CLOCKWISE)
    _scan_motor.reset_angle(0)
    _scan_motor.run_target(SCAN_SPEED, 0, wait=True)
    _has_motor  = True
except Exception:
    _has_motor  = False
    print("WARN:NO_SCAN_MOTOR")

try:
    _flag_motor = Motor(FLAG_MOTOR_PORT, Direction.CLOCKWISE)
    _flag_motor.reset_angle(0)
    _has_flag   = True
    print("INFO:FLAG_MOTOR_OK")
except Exception:
    _flag_motor = None
    _has_flag   = False
    print("WARN:NO_FLAG_MOTOR")

# ============================================================
# STATE
# ============================================================

current_mode     = 0
anim_counter     = 0
poems_frame      = 0
music_heights    = [urandom.randint(1, 5) for _ in range(5)]
in_menu          = False
menu_selection   = 0
sleeping         = False
last_activity_ms = 0
conv_listening   = False

in_attract            = False
attract_frame         = 0
attract_anim_ms       = 0
attract_lost_ms       = 0
attract_speaking      = False
ATTRACT_ANIM_FRAME_MS = 400

# ============================================================
# TICK / ACTIVITY
# ============================================================

_tick_counter = 0

def _elapsed_ms():
    return _tick_counter * ANIM_TICK_MS

def _inc_tick():
    global _tick_counter
    _tick_counter += 1

def poke_activity():
    global last_activity_ms
    last_activity_ms = _elapsed_ms()

# ============================================================
# SERIAL OUTPUT
# ============================================================

def emit(event, value=None):
    if value is None:
        print(event)
    else:
        print(f"{event}:{value}")

# ============================================================
# SERIAL INPUT — non-blocking
# ============================================================

def poll_serial():
    global _serial_buf
    if not _keyboard.poll(0):
        return None
    try:
        ch = stdin.buffer.read(1)
        if not ch:
            return None
        ch = ch.decode("utf-8", "ignore")
        if ch == "\n":
            line = _serial_buf.strip()
            _serial_buf = ""
            return line if line else None
        _serial_buf += ch
    except Exception:
        pass
    return None

def handle_pc_signal(line):
    global conv_listening

    emit("DEBUG", f"RX:{line}")

    if line == "CONV_LISTEN":
        conv_listening = True
        draw_conv_listening()

    elif line == "CONV_DONE":
        conv_listening = False
        if current_mode == 3:
            draw_conv_idle()

    elif line == "ATTRACT_SPEAK_START":
        global attract_speaking
        attract_speaking = True

    elif line == "ATTRACT_SPEAK_DONE":
        global attract_speaking
        attract_speaking = False

    elif line.startswith("MODE:"):
        try:
            idx = int(line.split(":")[1])
            enter_mode(idx)
        except Exception:
            pass

    elif line == "SLEEP":
        enter_sleep()

    elif line == "WAKE":
        if sleeping:
            exit_sleep()

    else:
        emit("WARN", f"UNKNOWN_CMD:{line}")

# ============================================================
# DRAWING
# ============================================================

def draw_icon(icon):
    hub.display.off()
    for r in range(5):
        for c in range(5):
            if icon[r][c]:
                hub.display.pixel(r, c, 100)

def draw_poems():
    draw_icon(rotate_right(POEMS_FRAMES[poems_frame % len(POEMS_FRAMES)]))

def draw_music():
    hub.display.off()
    for col in range(5):
        h = music_heights[col]
        for row in range(5 - h, 5):
            hub.display.pixel(row, 4 - col, 100)

def draw_conv_idle():
    draw_icon(CV_ICON)

def draw_conv_listening():
    draw_icon(MIC_ICON)

def draw_menu(sel):
    draw_icon(MODE_ICONS[sel % NUM_MODES])

def draw_attract_frame():
    draw_icon(ATTRACT_PULSE_FRAMES[attract_frame % len(ATTRACT_PULSE_FRAMES)])

# ============================================================
# SOUNDS
# ============================================================

def _play_tones(tones, gap_ms=20):
    for freq, dur in tones:
        hub.speaker.beep(frequency=freq, duration=dur)
        wait(gap_ms)

def play_mode_sound(mode_idx):  _play_tones(MODE_SOUNDS[mode_idx])
def play_sleep_sound():         _play_tones(SLEEP_SOUND, gap_ms=30)
def play_wake_sound():          _play_tones(WAKE_SOUND)
def play_attract_sad():         _play_tones(ATTRACT_SAD)

# ============================================================
# SLEEP / WAKE  — smooth 60° pendulum scan, no centre pause
# ============================================================

_last_distance = None

# Scan sequence: left extreme → right extreme → left extreme → ...
# No centre waypoint = continuous smooth swing, no pause at 0°.
_SCAN_LOGICAL       = [-60, 60]   # degrees: left, right
_scan_idx           = 0
_scan_target        = None
_scan_wait_until_ms = 0           # pause only at the extremes

# How long to dwell at each extreme before reversing (ms)
SCAN_DWELL_MS = 400

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

def _scan_step():
    """Called every SCAN_STEP_MS while sleeping.
    Drives motor in a smooth left↔right pendulum at 60° each side.
    No stop at centre — only a short dwell at each extreme."""
    global _scan_idx, _scan_target, _scan_wait_until_ms
    if not _has_motor:
        return
    try:
        # Still dwelling at the current extreme — do nothing
        if _elapsed_ms() < _scan_wait_until_ms:
            return

        target = _SCAN_LOGICAL[_scan_idx] + SCAN_OFFSET_DEG
        current_angle = _scan_motor.angle()

        if abs(current_angle - target) <= 8:
            # Reached the extreme — dwell briefly, then flip direction
            _scan_wait_until_ms = _elapsed_ms() + SCAN_DWELL_MS
            _scan_idx = (_scan_idx + 1) % len(_SCAN_LOGICAL)
            target = _SCAN_LOGICAL[_scan_idx] + SCAN_OFFSET_DEG

        if _scan_target != target:
            _scan_target = target
            _scan_motor.run_target(SCAN_SPEED, target, wait=False)
    except Exception:
        pass

def _motor_home():
    global _scan_target
    if not _has_motor:
        return
    try:
        _scan_motor.run_target(SCAN_SPEED, 0, wait=True)
        _scan_target = 0
    except Exception:
        pass

def enter_sleep():
    global sleeping, _scan_idx, in_attract, _scan_wait_until_ms
    sleeping            = True
    in_attract          = False
    _scan_idx           = 0
    _scan_wait_until_ms = 0          # ← reset dwell timer
    draw_icon(SLEEP_ICON)
    play_sleep_sound()
    emit("SLEEP")

def exit_sleep():
    global sleeping
    sleeping = False
    play_wake_sound()
    emit("WAKE")
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
    in_attract      = True
    attract_frame   = 0
    attract_anim_ms = 0
    attract_lost_ms = 0
    draw_attract_frame()
    play_mode_sound(4)
    emit("MODE", 4)
    emit("ATTRACT_ENTER")
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
    elif not attract_speaking:
        attract_lost_ms += ANIM_TICK_MS
        if attract_lost_ms >= ATTRACT_LOST_MS:
            attract_lost_ms = 0
            in_attract      = False
            emit("ATTRACT_LOST")
            emit("ATTRACT_TIMEOUT")

def exit_attract_to_menu():
    global in_attract
    in_attract = False
    emit("ATTRACT_EXIT")
    open_menu()

# ============================================================
# ANIMATION
# ============================================================

def update_anim():
    global anim_counter, poems_frame, music_heights
    if in_menu or sleeping or in_attract:
        return
    if current_mode in (0, 3, 4, 5):
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
# MODE ENTRY
# ============================================================

def enter_mode(mode_idx):
    global current_mode, anim_counter, poems_frame, music_heights
    global conv_listening, in_attract

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
    emit("MODE", current_mode)
    poke_activity()

# ============================================================
# MENU
# ============================================================

def open_menu():
    global in_menu, menu_selection
    in_menu        = True
    menu_selection = current_mode
    draw_menu(menu_selection)
    if current_mode in (1, 2):
        emit("MEDIA_PAUSE")
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
        emit("MEDIA_RESUME")
    enter_mode(menu_selection)

# ============================================================
# BUTTON HELPERS
# ============================================================

def _read_buttons():
    left = right = False
    if _has_force_btns:
        try:
            left  = _btn_left.pressed(BTN_FORCE_THRESHOLD)
            right = _btn_right.pressed(BTN_FORCE_THRESHOLD)
        except Exception:
            pass
    try:
        pressed = hub.buttons.pressed()
        left  = left  or (Button.LEFT  in pressed)
        right = right or (Button.RIGHT in pressed)
    except Exception:
        pass
    return left, right

def is_held(button, ms):
    elapsed = 0
    while True:
        left, right = _read_buttons()
        if not (left if button == 'left' else right):
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
# FLAG
# ============================================================

def init_flag():
    if not _has_flag:
        return
    try:
        _flag_motor.run(FLAG_SPEED)
    except Exception:
        pass

# ============================================================
# MAIN LOOP
# ============================================================

open_menu()
poke_activity()
emit("READY")
init_flag()
scan_tick = 0

while True:
    _inc_tick()

    line = poll_serial()
    if line:
        handle_pc_signal(line)

    # --- SLEEP ---
    if sleeping:
        scan_tick += ANIM_TICK_MS
        if scan_tick >= SCAN_STEP_MS:
            scan_tick = 0
            check_wake()
        sl, sr = _read_buttons()
        if sl or sr:
            poke_activity()
            exit_sleep()
        wait(ANIM_TICK_MS)
        continue

    # --- ATTRACT ---
    if in_attract:
        al, ar = _read_buttons()
        if al or ar:
            poke_activity()
            wait_release_all()
            wait(DEBOUNCE_MS)
            exit_attract_to_menu()
        else:
            tick_attract()
        wait(ANIM_TICK_MS)
        continue

    # --- INACTIVITY → SLEEP ---
    if _elapsed_ms() - last_activity_ms >= INACTIVITY_TIMEOUT_MS:
        enter_sleep()
        wait(ANIM_TICK_MS)
        continue

    # --- NORMAL OPERATION ---
    left_now, right_now = _read_buttons()

    if in_menu:
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
        if right_now:
            poke_activity()
            if is_held('right', HOLD_TIME_MS):
                hub.speaker.beep(frequency=1000, duration=200)
                wait_release_all()
                wait(DEBOUNCE_MS)
                emit("ACTION_HOLD")
            else:
                hub.speaker.beep(frequency=880, duration=100)
                wait_release_all()
                wait(DEBOUNCE_MS)
                emit("YES")

        elif left_now:
            poke_activity()
            if is_held('left', HOLD_TIME_MS):
                hub.speaker.beep(frequency=500, duration=200)
                wait_release_all()
                wait(DEBOUNCE_MS)
                open_menu()
            else:
                hub.speaker.beep(frequency=440, duration=100)
                wait_release_all()
                wait(DEBOUNCE_MS)
                emit("NO")

    update_anim()
    wait(ANIM_TICK_MS)