"""
vision/eye_animation.py
=======================
Friendly robot face with:
- Warm golden eye whites (not creepy blue)
- Dark pupils that follow gaze  
- Simple mouth for expressions
- Cute eyebrow animation
- Natural colors and smooth animations

Expressions:
  idle      - neutral, relaxed eyes and brows
  happy     - big squinted eyes + smile
  thinking  - puzzled eyebrows, neutral mouth
  speaking  - animated eyes with open look
  sleeping  - closed eyes, drooped appearance
"""

import logging
import threading
import time
import tkinter as tk
import math

logger = logging.getLogger(__name__)

# ── Canvas & Layout ────────────────────────────────────────────────────────────
WIN_W, WIN_H   = 640, 400
BG_COLOR       = "#1a1a2e"           # slightly warmer dark gray
FACE_COLOR     = "#0f3460"            # soft dark background for face area
MARGIN_H       = 60                   # top/bottom margin

# ── Eye Colors ─────────────────────────────────────────────────────────────────
EYE_WHITE      = "#f0e68c"           # warm golden-cream white (friendly!)
EYE_IRIS       = "#2d5a2d"           # warm green iris
EYE_PUPIL      = "#0a0a0a"           # dark pupil
EYE_OUTLINE    = "#d4af37"           # gold outline (warm & happy)

EYE_W          = 120
EYE_H          = 100
EYE_RADIUS     = 60                  # for rounded eye shape
PUPIL_RADIUS   = 16
IRIS_RADIUS    = 28

# ── Eyes Positioning ───────────────────────────────────────────────────────────
EYE_TOP        = WIN_H // 2 - 50
LEFT_EYE_X     = WIN_W // 2 - 110
RIGHT_EYE_X    = WIN_W // 2 + 50

# ── Mouth Positioning ──────────────────────────────────────────────────────────
MOUTH_X        = WIN_W // 2
MOUTH_Y        = WIN_H // 2 + 90
MOUTH_WIDTH    = 80
MOUTH_HEIGHT   = 30

# ── Brow Colors & Layout ───────────────────────────────────────────────────────
BROW_COLOR     = "#daa520"           # warm goldenrod (matches eye color)
BROW_H         = 14
BROW_GAP       = 30

# ── Animation timings ──────────────────────────────────────────────────────────
BLINK_INTERVAL = 4.0
BLINK_DURATION = 0.15
PUPIL_SMOOTHNESS = 0.15              # smooth pupil tracking


class EyeAnimator:
    """Friendly robot face with warm colors and expressive features."""

    def __init__(self):
        self._root   = None
        self._canvas = None
        self._running = False
        
        # Gaze tracking
        self._gaze_x  = 0.0
        self._gaze_y  = 0.0
        self._pupil_x = 0.0  # smoothed gaze
        self._pupil_y = 0.0
        
        # Blinking
        self._blink_open  = True
        self._last_blink  = time.time()
        
        # Expression & overlay
        self._expression  = "idle"
        self._overlay_text = ""
        self._text_expire  = 0.0
        
        # Thread safety
        self._pending_expression = None
        self._pending_text       = None
        self._lock = threading.Lock()

    def start(self):
        """Open the window. BLOCKS until closed. Call from MAIN thread only."""
        self._running = True
        self._tk_main()

    def stop(self):
        self._running = False
        if self._root:
            try:
                self._root.quit()
            except Exception:
                pass

    def tick(self):
        """Apply pending changes from other threads. Called by Tkinter scheduler."""
        with self._lock:
            expr = self._pending_expression
            text = self._pending_text
            self._pending_expression = None
            self._pending_text       = None
        if expr is not None:
            self._expression = expr
        if text is not None:
            self._overlay_text = text
            self._text_expire  = time.time() + 4.0
        if self._overlay_text and time.time() > self._text_expire:
            self._overlay_text = ""

    def set_expression(self, expression: str):
        """Change the robot's facial expression."""
        with self._lock:
            self._pending_expression = expression

    def set_gaze(self, x_norm: float, y_norm: float):
        """Update where the robot is looking (normalized -1 to +1)."""
        self._gaze_x = max(-1.0, min(1.0, x_norm))
        self._gaze_y = max(-1.0, min(1.0, y_norm))

    def show_text(self, text: str):
        """Display text overlay on the robot face."""
        with self._lock:
            self._pending_text = text

    def _tk_main(self):
        """Initialize Tkinter window."""
        self._root = tk.Tk()
        self._root.title("Esperanto Roboto 🤖")
        self._root.configure(bg=BG_COLOR)
        self._root.resizable(False, False)
        self._canvas = tk.Canvas(
            self._root, width=WIN_W, height=WIN_H,
            bg=BG_COLOR, highlightthickness=0
        )
        self._canvas.pack()
        self._root.after(30, self._frame)
        self._root.mainloop()

    def _frame(self):
        """Main animation loop (called every 30ms)."""
        if not self._running:
            return
        self.tick()
        self._update_blink()
        self._smooth_gaze()
        self._draw()
        self._root.after(30, self._frame)

    def _update_blink(self):
        """Handle eye blinking."""
        now = time.time()
        if self._expression == "sleeping":
            self._blink_open = False
            return
        if not self._blink_open and now - self._last_blink > BLINK_DURATION:
            self._blink_open = True
        if self._blink_open and now - self._last_blink > BLINK_INTERVAL:
            self._blink_open = False
            self._last_blink = now

    def _smooth_gaze(self):
        """Smoothly track gaze position."""
        self._pupil_x += (self._gaze_x - self._pupil_x) * PUPIL_SMOOTHNESS
        self._pupil_y += (self._gaze_y - self._pupil_y) * PUPIL_SMOOTHNESS

    def _draw(self):
        """Draw the entire face."""
        c = self._canvas
        c.delete("all")
        
        # Background
        c.create_rectangle(0, 0, WIN_W, WIN_H, fill=BG_COLOR, outline="")
        
        # Face background (subtle)
        padding = 80
        c.create_oval(padding, MARGIN_H - 30, WIN_W - padding, WIN_H - MARGIN_H + 30,
                      fill=FACE_COLOR, outline="", width=0)
        
        # Draw eyes and mouth
        self._draw_eye(c, LEFT_EYE_X, EYE_TOP)
        self._draw_eye(c, RIGHT_EYE_X, EYE_TOP)
        self._draw_mouth(c, self._expression)
        self._draw_eyebrows(c, self._expression)
        
        # Debug text overlay
        if self._overlay_text:
            c.create_text(
                WIN_W // 2, 30,
                text=self._overlay_text,
                font=("Arial", 24, "bold"),
                fill=EYE_OUTLINE,
            )

    def _draw_eye(self, c, cx, cy):
        """Draw a single eye with iris, pupil, and reflection."""
        expr = self._expression
        blink = not self._blink_open
        
        # Eye white (outer oval)
        c.create_oval(
            cx - EYE_RADIUS, cy - EYE_RADIUS,
            cx + EYE_RADIUS, cy + EYE_RADIUS,
            fill=EYE_WHITE, outline=EYE_OUTLINE, width=3
        )
        
        # Eyelid closing effect when blinking
        if blink:
            blink_amount = 0.95
            c.create_oval(
                cx - EYE_RADIUS, cy - EYE_RADIUS,
                cx + EYE_RADIUS, cy + EYE_RADIUS * blink_amount,
                fill=BG_COLOR, outline="", width=0
            )
            c.create_oval(
                cx - EYE_RADIUS, cy - EYE_RADIUS * (1 - blink_amount),
                cx + EYE_RADIUS, cy + EYE_RADIUS,
                fill=BG_COLOR, outline="", width=0
            )
            return  # Skip iris/pupil when blinking
        
        # Iris
        iris_x = cx + int(self._pupil_x * 20)
        iris_y = cy + int(self._pupil_y * 16)
        c.create_oval(
            iris_x - IRIS_RADIUS, iris_y - IRIS_RADIUS,
            iris_x + IRIS_RADIUS, iris_y + IRIS_RADIUS,
            fill=EYE_IRIS, outline=EYE_OUTLINE, width=2
        )
        
        # Pupil
        pupil_x = iris_x + int(self._pupil_x * 8)
        pupil_y = iris_y + int(self._pupil_y * 6)
        c.create_oval(
            pupil_x - PUPIL_RADIUS, pupil_y - PUPIL_RADIUS,
            pupil_x + PUPIL_RADIUS, pupil_y + PUPIL_RADIUS,
            fill=EYE_PUPIL, outline=""
        )
        
        # Highlight (shine in pupil)
        shine_x = pupil_x - 6
        shine_y = pupil_y - 6
        c.create_oval(
            shine_x - 4, shine_y - 4,
            shine_x + 4, shine_y + 4,
            fill="#ffffff", outline=""
        )

    def _draw_mouth(self, c, expr):
        """Draw mouth based on expression."""
        if expr == "sleeping":
            # Closed smile
            c.create_arc(
                MOUTH_X - 40, MOUTH_Y - 10,
                MOUTH_X + 40, MOUTH_Y + 30,
                start=0, extent=180,
                outline=EYE_OUTLINE, width=3
            )
        elif expr == "happy":
            # Big smile
            c.create_arc(
                MOUTH_X - 60, MOUTH_Y - 15,
                MOUTH_X + 60, MOUTH_Y + 35,
                start=0, extent=180,
                outline=EYE_OUTLINE, width=4, fill="#f0e68c"
            )
            # Cheeks
            c.create_oval(
                MOUTH_X - 130, MOUTH_Y - 20,
                MOUTH_X - 100, MOUTH_Y + 10,
                fill="#ff9999", outline="", width=0
            )
            c.create_oval(
                MOUTH_X + 100, MOUTH_Y - 20,
                MOUTH_X + 130, MOUTH_Y + 10,
                fill="#ff9999", outline="", width=0
            )
        elif expr == "speaking":
            # Open mouth (O shape)
            c.create_oval(
                MOUTH_X - 25, MOUTH_Y - 20,
                MOUTH_X + 25, MOUTH_Y + 20,
                fill=EYE_OUTLINE, outline=EYE_OUTLINE, width=2
            )
        elif expr == "thinking":
            # Neutral / slight frown
            c.create_arc(
                MOUTH_X - 50, MOUTH_Y + 5,
                MOUTH_X + 50, MOUTH_Y + 40,
                start=0, extent=180,
                outline=EYE_OUTLINE, width=2
            )
        else:  # idle, etc
            # Neutral closed mouth
            c.create_line(
                MOUTH_X - 40, MOUTH_Y,
                MOUTH_X + 40, MOUTH_Y,
                fill=EYE_OUTLINE, width=2
            )

    def _draw_eyebrows(self, c, expr):
        """Draw expressive eyebrows."""
        base_y = EYE_TOP - 50
        left_brow_x = LEFT_EYE_X + EYE_RADIUS
        right_brow_x = RIGHT_EYE_X + EYE_RADIUS
        
        if expr == "idle":
            # Neutral, slightly arched
            y_out = base_y - 10
            y_in = base_y - 5
        elif expr == "happy":
            # High arch, very happy
            y_out = base_y - 25
            y_in = base_y - 8
        elif expr == "thinking":
            # Inner corners raised (puzzled)
            y_out = base_y
            y_in = base_y - 20
        elif expr == "speaking":
            # Slightly raised, animated
            y_out = base_y - 12
            y_in = base_y - 6
        elif expr == "sleeping":
            # Drooped
            y_out = base_y - 5
            y_in = base_y + 15
        else:
            y_out = y_in = base_y - 5
        
        # Left brow (outer → inner)
        c.create_line(
            LEFT_EYE_X - 20, y_out,
            left_brow_x + 20, y_in,
            fill=BROW_COLOR, width=BROW_H, capstyle=tk.ROUND
        )
        
        # Right brow (inner → outer)
        c.create_line(
            RIGHT_EYE_X - 20, y_in,
            right_brow_x + 20, y_out,
            fill=BROW_COLOR, width=BROW_H, capstyle=tk.ROUND
        )