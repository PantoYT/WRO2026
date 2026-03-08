from pybricks.hubs import PrimeHub
from pybricks.parameters import Button
from pybricks.tools import wait

# === KONFIGURACJA ===
LEFT_BUTTON  = Button.LEFT
RIGHT_BUTTON = Button.RIGHT
HOLD_TIME_MS = 800
DEBOUNCE_MS  = 600  # ignoruj inputy przez X ms po akcji
SPEAKER_VOLUME = 20
# ====================

hub = PrimeHub()
hub.speaker.volume(SPEAKER_VOLUME)

def is_held(button, ms):
    elapsed = 0
    while button in hub.buttons.pressed():
        wait(50)
        elapsed += 50
        if elapsed >= ms:
            return True
    return False

def wait_release():
    while hub.buttons.pressed():
        wait(50)

# sygnał gotowości dla computer.py
print("READY")

while True:
    pressed = hub.buttons.pressed()

    if RIGHT_BUTTON in pressed:
        if is_held(RIGHT_BUTTON, HOLD_TIME_MS):
            hub.speaker.beep(frequency=1000, duration=200)
            wait_release()
            wait(DEBOUNCE_MS)
            print("DEFINE")
        else:
            hub.speaker.beep(frequency=880, duration=100)
            wait_release()
            wait(DEBOUNCE_MS)
            print("YES")

    elif LEFT_BUTTON in pressed:
        hub.speaker.beep(frequency=440, duration=100)
        wait_release()
        wait(DEBOUNCE_MS)
        print("NO")

    wait(50)