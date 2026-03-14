from pybricks.hubs import PrimeHub
from pybricks.parameters import Button, Direction, Port, Stop
from pybricks.pupdevices import ColorSensor, Motor
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

NUM_MODES = 3

HUB_BUTTONS = [
    (Button.RIGHT, "YES",  "ACTION_HOLD"),
    (Button.LEFT,  "NO",   "MODE"),
]

# --- Zewnętrzne wejścia (odkomentuj + uzupełnij port) ---
# MOTOR_PORT       = Port.A
# MOTOR_PRESS_DEG  = 30
# MOTOR_HOLD_MS    = 500
# MOTOR_RETURN_SPD = 200
# MOTOR_ACTIONS    = ("MOTOR_YES", "MOTOR_ACTION_HOLD")

# LIGHT_PORT       = Port.B
# LIGHT_THRESHOLD  = 50
# LIGHT_HOLD_MS    = 800
# LIGHT_ACTIONS    = ("LIGHT_YES", "LIGHT_ACTION_HOLD")

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
    [O, O, I, O, O],
    [O, O, I, O, O],
    [O, O, I, O, O],
    [O, O, O, O, O],
    [O, O, I, O, O],
]

MU_ICON = [
    [O, O, O, I, O],
    [O, I, O, I, O],
    [I, I, O, I, O],
    [I, I, O, I, I],
    [I, I, I, I, I],
]

MODE_ICONS = [FC_ICON, PO_ICON, MU_ICON]
MODE_NAMES = ["FLASHCARDS", "POEMS", "MUSIC"]

MODE_SOUNDS = [
    [(523, 80), (659, 120)],             
    [(440, 60), (440, 60), (554, 150)],  
    [(330, 50), (415, 50), (523, 50), (659, 100)],
]

# ============================================================
# POEMS — ramki znaków interpunkcyjnych
# ============================================================

POEMS_FRAMES = [
    # "."
    [[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,I,O,O]],
    # ","
    [[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,I,O,O],[O,I,O,O,O]],
    # ";"
    [[O,O,O,O,O],[O,O,I,O,O],[O,O,O,O,O],[O,O,I,O,O],[O,I,O,O,O]],
    # ":"
    [[O,O,O,O,O],[O,O,I,O,O],[O,O,O,O,O],[O,O,I,O,O],[O,O,O,O,O]],
    # "!"
    [[O,O,I,O,O],[O,O,I,O,O],[O,O,I,O,O],[O,O,O,O,O],[O,O,I,O,O]],
    # "?"
    [[O,I,I,I,O],[O,O,O,I,O],[O,O,I,O,O],[O,O,O,O,O],[O,O,I,O,O]],
    # '"'
    [[O,I,O,I,O],[O,I,O,I,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O]],
    # "'"
    [[O,O,I,O,O],[O,O,I,O,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O]],
    # "…"
    [[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O],[O,O,O,O,O],[I,O,I,O,I]],
    # "-"
    [[O,O,O,O,O],[O,O,O,O,O],[O,I,I,I,O],[O,O,O,O,O],[O,O,O,O,O]],
]

# ============================================================
# INICJALIZACJA
# ============================================================

hub = PrimeHub()
hub.speaker.volume(SPEAKER_VOLUME)

# _motor = Motor(MOTOR_PORT, Direction.CLOCKWISE)
# _motor.reset_angle(0)
# _light = ColorSensor(LIGHT_PORT)

# ============================================================
# STAN
# ============================================================

current_mode   = 0
anim_counter   = 0
poems_frame    = 0
music_heights  = [urandom.randint(1, 5) for _ in range(5)]
in_menu        = False
menu_selection = 0

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

def draw_menu(sel):
    """Menu wyboru trybu — pełna ikona wybranego trybu."""
    hub.display.off()
    icon = MODE_ICONS[sel % NUM_MODES]
    for r in range(5):
        for c in range(5):
            if icon[r][c]:
                hub.display.pixel(r, c, 100)

def play_mode_sound(mode_idx):
    for freq, dur in MODE_SOUNDS[mode_idx]:
        hub.speaker.beep(frequency=freq, duration=dur)
        wait(20)

# ============================================================
# ANIMACJA (wywoływana co tick)
# ============================================================

def update_anim():
    global anim_counter, poems_frame, music_heights
    if in_menu:
        return
    if current_mode == 0:
        return  # FC statyczny
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
    global current_mode, anim_counter, poems_frame, music_heights
    current_mode  = mode_idx % NUM_MODES
    anim_counter  = 0
    if current_mode == 0:
        draw_icon(FC_ICON)
    elif current_mode == 1:
        poems_frame = 0
        draw_poems()
    elif current_mode == 2:
        music_heights = [urandom.randint(1, 5) for _ in range(5)]
        draw_music()
    play_mode_sound(current_mode)
    print(f"MODE:{current_mode}")

# ============================================================
# MENU TRYBU
# ============================================================

def open_menu():
    global in_menu, menu_selection
    in_menu        = True
    menu_selection = current_mode
    draw_menu(menu_selection)
    hub.speaker.beep(frequency=600, duration=100)
    wait(120)
    hub.speaker.beep(frequency=800, duration=100)

def menu_cycle():
    """Prawy przycisk w menu — cykluj po trybach."""
    global menu_selection
    menu_selection = (menu_selection + 1) % NUM_MODES
    draw_menu(menu_selection)
    hub.speaker.beep(frequency=700, duration=80)

def menu_confirm():
    """Lewy przycisk w menu — zatwierdź wybrany tryb."""
    global in_menu
    in_menu = False
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
# GŁÓWNA PĘTLA
# ============================================================

open_menu()
print("READY")

while True:
    pressed = hub.buttons.pressed()

    if in_menu:
        if Button.RIGHT in pressed:
            wait_release_all()
            wait(DEBOUNCE_MS)
            menu_cycle()
        elif Button.LEFT in pressed:
            wait_release_all()
            wait(DEBOUNCE_MS)
            menu_confirm()

    else:
        for (btn, short_action, long_action) in HUB_BUTTONS:
            if btn in pressed:
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