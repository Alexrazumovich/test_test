from __future__ import annotations

import math
import random
import tkinter as tk
from typing import List, Optional, Tuple

from logic import GameLogic, Vector2, Color, Ball, Rect


# ----------------------------
# Configuration
# ----------------------------
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 600
TARGET_FPS = 60
INITIAL_BALLS = 50  # start amount

# Deletion zone rectangle (in canvas/world coordinates)
DELETION_ZONE = Rect(x=WINDOW_WIDTH - 180, y=40, width=140, height=90)


class BallGameApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Ball Mixer")

        self.canvas = tk.Canvas(root, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Backing logic world
        self.logic = GameLogic(width=WINDOW_WIDTH, height=WINDOW_HEIGHT, random_seed=42)
        self.logic.set_deletion_zone(DELETION_ZONE)

        # Populate initial balls
        self._spawn_initial_balls(INITIAL_BALLS)

        # Mouse interaction state
        self.mouse_pos: Optional[Tuple[float, float]] = None
        self.is_sucking: bool = False
        self.last_spit_dir: Optional[Tuple[float, float]] = None

        # Bindings
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down_left)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up_left)
        self.canvas.bind("<ButtonPress-3>", self._on_mouse_down_right)

        # Animation
        self._last_time_ms: Optional[int] = None
        self._tick()

    # ----------------------------
    # Setup helpers
    # ----------------------------
    def _spawn_initial_balls(self, count: int) -> None:
        rng = random.Random(7)
        for _ in range(count):
            x = rng.uniform(30, WINDOW_WIDTH - 30)
            y = rng.uniform(30, WINDOW_HEIGHT - 30)
            speed = rng.uniform(30, 120)
            angle = rng.uniform(0, 2 * math.pi)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            radius = rng.uniform(7, 14)

            # rainbow-ish palette
            h = rng.random()
            s = 0.7 + 0.3 * rng.random()
            v = 0.8 + 0.2 * rng.random()
            color = Color.from_hsv(h, s, v)

            self.logic.create_ball(Vector2(x, y), Vector2(vx, vy), radius, color)

    # ----------------------------
    # Event handlers
    # ----------------------------
    def _on_mouse_move(self, event: tk.Event) -> None:
        self.mouse_pos = (event.x, event.y)

        # For right-click spit direction, remember last motion delta
        if self.last_spit_dir is not None and self.mouse_pos is not None:
            pass

    def _on_mouse_down_left(self, event: tk.Event) -> None:
        self.is_sucking = True
        self.mouse_pos = (event.x, event.y)

    def _on_mouse_up_left(self, event: tk.Event) -> None:
        self.is_sucking = False

    def _on_mouse_down_right(self, event: tk.Event) -> None:
        # Spit from inventory in the direction of recent mouse motion (or random if none)
        point = Vector2(event.x, event.y)
        direction = None
        if self.mouse_pos is not None:
            dx = event.x - self.mouse_pos[0]
            dy = event.y - self.mouse_pos[1]
            if abs(dx) + abs(dy) > 0.01:
                direction = Vector2(dx, dy)
        self.logic.spit_from_inventory(point, direction, count=3)

    # ----------------------------
    # Animation and rendering
    # ----------------------------
    def _tick(self) -> None:
        now = self.root.winfo_fpixels("1i")  # placeholder to ensure Tk is initialized
        # Use Tk's timer for dt
        cur_ms = self.root.winfo_pointerx()  # not ideal; we will fall back to fixed dt
        dt = 1.0 / TARGET_FPS

        # Suck behavior when holding left mouse
        if self.is_sucking and self.mouse_pos is not None:
            suck_point = Vector2(self.mouse_pos[0], self.mouse_pos[1])
            self.logic.suck_into_inventory(suck_point, radius=60.0, max_count=4)

        # Update world
        self.logic.update(dt)

        # Redraw
        self._render()

        # Schedule next frame
        self.root.after(int(1000 / TARGET_FPS), self._tick)

    def _render(self) -> None:
        self.canvas.delete("all")
        self._draw_deletion_zone()
        balls = self.logic.list_balls()
        for b in balls:
            self._draw_ball(b)
        # Inventory count HUD
        inv = len(self.logic.inventory)
        self.canvas.create_text(10, 10, anchor="nw", text=f"Inventory: {inv}", fill="#333", font=("Arial", 12))

        # Cursor visual if sucking
        if self.is_sucking and self.mouse_pos is not None:
            x, y = self.mouse_pos
            r = 60
            self.canvas.create_oval(x - r, y - r, x + r, y + r, outline="#888", dash=(3, 3))

    def _draw_ball(self, ball: Ball) -> None:
        x = ball.position.x
        y = ball.position.y
        r = ball.radius
        fill = self._color_to_hex(ball.color)
        self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline="")

    def _draw_deletion_zone(self) -> None:
        dz = self.logic.deletion_zone
        if dz is None:
            return
        x0 = dz.x
        y0 = dz.y
        x1 = dz.x + dz.width
        y1 = dz.y + dz.height
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="#d33", width=2)
        self.canvas.create_text((x0 + x1) / 2, y0 + 14, text="Delete Zone", fill="#d33", font=("Arial", 12, "bold"))

    @staticmethod
    def _color_to_hex(c: Color) -> str:
        r = int(max(0, min(255, round(c.r * 255))))
        g = int(max(0, min(255, round(c.g * 255))))
        b = int(max(0, min(255, round(c.b * 255))))
        return f"#{r:02x}{g:02x}{b:02x}"


def main() -> None:
    root = tk.Tk()
    app = BallGameApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
