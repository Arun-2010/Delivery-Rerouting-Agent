"""Depot, drivers, delivery stops, and the in-memory state the agent edits."""

import math
import random
from dataclasses import dataclass, field

Point = tuple[float, float]  # (latitude, longitude)

DEPOT: Point = (33.5731, -7.5898)  # Casablanca center
ALL_DRIVERS: list[str] = ["Driver 1", "Driver 2", "Driver 3"]
MAX_STOPS_PER_DRIVER = 6

NUM_STOPS = 12
STOP_RADIUS_KM = 8.0
SEED = 42

EARTH_RADIUS_KM = 6371.0
KM_PER_DEGREE_LAT = 111.32


def haversine_km(a: Point, b: Point) -> float:
    """Straight-line distance in km between two (lat, lon) points."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def generate_stops(n: int = NUM_STOPS, radius_km: float = STOP_RADIUS_KM, seed: int = SEED) -> dict[int, Point]:
    """Random stops within radius_km of the depot. Same seed -> same stops."""
    rng = random.Random(seed)
    stops = {}
    for stop_id in range(1, n + 1):
        # sqrt() spreads points evenly over the disk instead of bunching them at the center.
        distance = radius_km * math.sqrt(rng.random())
        angle = rng.uniform(0, 2 * math.pi)
        dlat = distance * math.sin(angle) / KM_PER_DEGREE_LAT
        dlon = distance * math.cos(angle) / (KM_PER_DEGREE_LAT * math.cos(math.radians(DEPOT[0])))
        stops[stop_id] = (round(DEPOT[0] + dlat, 5), round(DEPOT[1] + dlon, 5))
    return stops


ALL_STOPS: dict[int, Point] = generate_stops()


@dataclass
class State:
    """What is true right now: who can drive, what must be delivered, and the latest plan."""

    drivers: list[str] = field(default_factory=lambda: list(ALL_DRIVERS))
    stops: dict[int, Point] = field(default_factory=lambda: dict(ALL_STOPS))
    last_plan: dict | None = None


# The one shared state object. Tools and the UI read and change it.
state = State()


def reset() -> None:
    """Bring back all drivers and stops, and forget the last plan."""
    fresh = State()
    state.drivers = fresh.drivers
    state.stops = fresh.stops
    state.last_plan = fresh.last_plan


if __name__ == "__main__":
    print("Depot:", DEPOT)
    print("Drivers:", state.drivers)
    for stop_id, point in state.stops.items():
        print(f"Stop {stop_id:>2}: {point}  ({haversine_km(DEPOT, point):.1f} km from depot)")
