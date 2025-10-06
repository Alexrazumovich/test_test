from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple
import math
import random
import colorsys


@dataclass
class Vector2:
    x: float
    y: float

    def add(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x + other.x, self.y + other.y)

    def sub(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x - other.x, self.y - other.y)

    def mul(self, scalar: float) -> "Vector2":
        return Vector2(self.x * scalar, self.y * scalar)

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> "Vector2":
        length = self.length()
        if length == 0:
            return Vector2(0.0, 0.0)
        return Vector2(self.x / length, self.y / length)


@dataclass
class Color:
    r: float  # 0..1
    g: float  # 0..1
    b: float  # 0..1

    def clamp(self) -> "Color":
        return Color(
            r=min(1.0, max(0.0, self.r)),
            g=min(1.0, max(0.0, self.g)),
            b=min(1.0, max(0.0, self.b)),
        )

    def to_hsv(self) -> Tuple[float, float, float]:
        return colorsys.rgb_to_hsv(self.r, self.g, self.b)

    @staticmethod
    def from_hsv(h: float, s: float, v: float) -> "Color":
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return Color(r, g, b)


@dataclass
class Ball:
    ball_id: int
    position: Vector2
    velocity: Vector2
    radius: float
    color: Color


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float

    def contains(self, p: Vector2) -> bool:
        return self.x <= p.x <= self.x + self.width and self.y <= p.y <= self.y + self.height


def _circular_mean_hue(hues: List[float], weights: List[float]) -> float:
    if not hues:
        return 0.0
    tw = max(1e-9, sum(weights))
    angles = [h * 2.0 * math.pi for h in hues]
    x = sum(math.cos(a) * w for a, w in zip(angles, weights)) / tw
    y = sum(math.sin(a) * w for a, w in zip(angles, weights)) / tw
    angle = math.atan2(y, x)
    if angle < 0:
        angle += 2.0 * math.pi
    return angle / (2.0 * math.pi)


def mix_colors(c1: Color, c2: Color) -> Color:
    """
    Blend two colors to avoid boring white/gray results.

    Strategy:
    - Compute circular mean of hues weighted by chroma (saturation*value)
    - Increase saturation via complement rule (1 - Π(1 - s)) to keep results vivid
    - Use geometric mean for value (brightness) to avoid drifting to white
    - Small post-boost to saturation
    """
    h1, s1, v1 = c1.to_hsv()
    h2, s2, v2 = c2.to_hsv()

    chroma1 = s1 * v1
    chroma2 = s2 * v2
    h = _circular_mean_hue([h1, h2], [chroma1 + 1e-6, chroma2 + 1e-6])

    # Saturation: combine to stay colorful
    s = 1.0 - (1.0 - s1) * (1.0 - s2)
    s = min(1.0, max(0.0, s * 1.05))

    # Value: geometric mean to avoid whitening
    v = math.sqrt(max(0.0, v1) * max(0.0, v2))

    # Convert back and clamp
    mixed = Color.from_hsv(h, s, v).clamp()
    return mixed


class GameLogic:
    def __init__(
        self,
        width: float,
        height: float,
        *,
        initial_balls: Optional[Iterable[Ball]] = None,
        inventory_capacity: Optional[int] = None,
        random_seed: Optional[int] = None,
    ) -> None:
        self.width = float(width)
        self.height = float(height)
        self._balls: Dict[int, Ball] = {}
        self._next_id: int = 1
        if initial_balls:
            for b in initial_balls:
                self._balls[b.ball_id] = b
                self._next_id = max(self._next_id, b.ball_id + 1)
        self.inventory_capacity = inventory_capacity
        self.inventory: List[Ball] = []
        self.deletion_zone: Optional[Rect] = None
        self._rng = random.Random(random_seed)

    # ----------------------------
    # Ball lifecycle
    # ----------------------------
    def create_ball(self, position: Vector2, velocity: Vector2, radius: float, color: Color) -> Ball:
        ball = Ball(ball_id=self._next_id, position=position, velocity=velocity, radius=radius, color=color)
        self._next_id += 1
        self._balls[ball.ball_id] = ball
        return ball

    def remove_ball(self, ball_id: int) -> None:
        if ball_id in self._balls:
            del self._balls[ball_id]

    def list_balls(self) -> List[Ball]:
        return list(self._balls.values())

    # ----------------------------
    # World configuration
    # ----------------------------
    def set_deletion_zone(self, rect: Optional[Rect]) -> None:
        self.deletion_zone = rect

    # ----------------------------
    # Update loop
    # ----------------------------
    def update(self, dt: float) -> None:
        if dt <= 0:
            return

        # 1) Integrate motion with screen wrap
        for ball in list(self._balls.values()):
            ball.position = ball.position.add(ball.velocity.mul(dt))
            # toroidal wrap-around
            ball.position.x %= self.width
            ball.position.y %= self.height

        # 2) Delete balls inside deletion zone
        if self.deletion_zone is not None:
            to_delete: List[int] = []
            for ball in self._balls.values():
                if self.deletion_zone.contains(ball.position):
                    to_delete.append(ball.ball_id)
            for bid in to_delete:
                self.remove_ball(bid)

        # 3) Color mixing on contact (no repulsion)
        self._apply_color_mixing()

    # ----------------------------
    # Inventory mechanics
    # ----------------------------
    def suck_into_inventory(self, point: Vector2, radius: float, max_count: Optional[int] = None) -> List[Ball]:
        """
        Pull nearby balls (within radius from point) into the inventory.
        Returns the list of sucked balls.
        """
        candidates: List[Tuple[float, Ball]] = []
        r2 = radius * radius
        for ball in self._balls.values():
            dx = ball.position.x - point.x
            dy = ball.position.y - point.y
            if dx * dx + dy * dy <= r2:
                dist = math.hypot(dx, dy)
                candidates.append((dist, ball))

        candidates.sort(key=lambda t: t[0])

        sucked: List[Ball] = []
        for _, ball in candidates:
            if max_count is not None and len(sucked) >= max_count:
                break
            if self.inventory_capacity is not None and len(self.inventory) >= self.inventory_capacity:
                break
            self._balls.pop(ball.ball_id, None)
            self.inventory.append(ball)
            sucked.append(ball)
        return sucked

    def spit_from_inventory(
        self,
        point: Vector2,
        direction: Optional[Vector2] = None,
        *,
        count: int = 1,
        base_speed: float = 200.0,
        spread_degrees: float = 20.0,
    ) -> List[Ball]:
        """
        Eject up to `count` balls back into the world at `point`.
        If `direction` is given, velocities are oriented roughly along it with some spread.
        """
        emitted: List[Ball] = []
        direction_norm = None if direction is None else direction.normalized()

        for _ in range(min(count, len(self.inventory))):
            ball = self.inventory.pop()  # LIFO feels responsive
            ball.position = Vector2(point.x, point.y)
            if direction_norm is None:
                angle = self._rng.uniform(0.0, 2.0 * math.pi)
            else:
                base_angle = math.atan2(direction_norm.y, direction_norm.x)
                spread = math.radians(spread_degrees)
                angle = base_angle + self._rng.uniform(-spread * 0.5, spread * 0.5)
            speed = base_speed * (0.85 + 0.30 * self._rng.random())
            ball.velocity = Vector2(math.cos(angle) * speed, math.sin(angle) * speed)
            self._balls[ball.ball_id] = ball
            emitted.append(ball)
        return emitted

    # ----------------------------
    # Internals
    # ----------------------------
    def _apply_color_mixing(self) -> None:
        # Spatial hashing to reduce pair checks
        cell_size = max(32.0, self._estimate_cell_size())
        grid: Dict[Tuple[int, int], List[Ball]] = {}
        for ball in self._balls.values():
            cx = int(ball.position.x // cell_size)
            cy = int(ball.position.y // cell_size)
            grid.setdefault((cx, cy), []).append(ball)

        visited: set[Tuple[int, int]] = set()
        for (cx, cy), bucket in grid.items():
            # Check this cell and neighbors
            neighbors: List[Ball] = []
            for ny in (-1, 0, 1):
                for nx in (-1, 0, 1):
                    key = (cx + nx, cy + ny)
                    if key in grid:
                        neighbors.extend(grid[key])

            # For each ball in current bucket, check overlaps with neighbors
            for i, a in enumerate(bucket):
                for b in neighbors:
                    if a.ball_id >= b.ball_id:
                        continue
                    self._maybe_mix(a, b)

    def _maybe_mix(self, a: Ball, b: Ball) -> None:
        dx = b.position.x - a.position.x
        dy = b.position.y - a.position.y
        dist2 = dx * dx + dy * dy
        r = a.radius + b.radius
        if dist2 <= r * r:
            mixed = mix_colors(a.color, b.color)
            a.color = mixed
            b.color = mixed

    def _estimate_cell_size(self) -> float:
        # Heuristic: twice the average radius
        balls = self.list_balls()
        if not balls:
            return 64.0
        avg_r = sum(b.radius for b in balls) / len(balls)
        return max(16.0, min(128.0, avg_r * 2.5))

    # ----------------------------
    # Introspection helpers for UI/Tests
    # ----------------------------
    def snapshot(self) -> Dict:
        return {
            "width": self.width,
            "height": self.height,
            "balls": [
                {
                    "id": b.ball_id,
                    "x": b.position.x,
                    "y": b.position.y,
                    "vx": b.velocity.x,
                    "vy": b.velocity.y,
                    "r": b.radius,
                    "color": {"r": b.color.r, "g": b.color.g, "b": b.color.b},
                }
                for b in self.list_balls()
            ],
            "inventory_count": len(self.inventory),
            "deletion_zone": None
            if self.deletion_zone is None
            else {
                "x": self.deletion_zone.x,
                "y": self.deletion_zone.y,
                "w": self.deletion_zone.width,
                "h": self.deletion_zone.height,
            },
        }


__all__ = [
    "Vector2",
    "Color",
    "Ball",
    "Rect",
    "GameLogic",
    "mix_colors",
]


