"""Route planning with Google OR-Tools, plus a separate rule check."""

from collections import Counter

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from data import DEPOT, MAX_STOPS_PER_DRIVER, Point, haversine_km

TIME_LIMIT_SECONDS = 2


def distance_matrix_m(points: list[Point]) -> list[list[int]]:
    """Distances in integer meters between every pair of points (OR-Tools needs integers)."""
    return [[round(haversine_km(a, b) * 1000) for b in points] for a in points]


def plan_routes(drivers: list[str], stops: dict[int, Point], max_stops: int = MAX_STOPS_PER_DRIVER) -> dict:
    """Assign stops to drivers and order them to minimize total distance.

    Returns {"status": "ok", "routes", "distance_km", "total_km"}, or a dict with
    status "no_drivers" / "no_stops" / "infeasible" and a plain-English "reason".
    """
    if not drivers:
        return {"status": "no_drivers", "reason": "No drivers are available, so no routes can be planned."}
    if not stops:
        return {"status": "no_stops", "reason": "There are no stops to deliver."}

    capacity = len(drivers) * max_stops
    if len(stops) > capacity:
        return {
            "status": "infeasible",
            "reason": (
                f"{len(stops)} stops but only {len(drivers)} driver(s) x {max_stops} stops = "
                f"{capacity} stops of capacity. {len(stops) - capacity} stop(s) cannot be covered."
            ),
        }

    # Node 0 is the depot; node i (i >= 1) is stop stop_ids[i - 1].
    stop_ids = sorted(stops)
    points = [DEPOT] + [stops[s] for s in stop_ids]
    matrix = distance_matrix_m(points)

    # The manager translates between OR-Tools' internal indices and our node numbers.
    # Every vehicle starts and ends at node 0 (the depot).
    manager = pywrapcp.RoutingIndexManager(len(points), len(drivers), 0)
    routing = pywrapcp.RoutingModel(manager)

    # Cost of travelling between two nodes = distance in meters.
    def distance_callback(from_index: int, to_index: int) -> int:
        return matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    distance_cb = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(distance_cb)

    # "Stops" dimension: each visit to a stop adds 1, the depot adds 0.
    # Capping the running total at max_stops is the hard "at most 6 stops" rule.
    def count_callback(from_index: int) -> int:
        return 0 if manager.IndexToNode(from_index) == 0 else 1

    count_cb = routing.RegisterUnaryTransitCallback(count_callback)
    routing.AddDimension(count_cb, 0, max_stops, True, "Stops")  # no slack, cap, start at zero

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = TIME_LIMIT_SECONDS

    solution = routing.SolveWithParameters(params)
    if solution is None:
        return {"status": "infeasible", "reason": "The solver could not find a plan that respects the rules."}

    routes: dict[str, list[int]] = {}
    distance_km: dict[str, float] = {}
    for vehicle, driver in enumerate(drivers):
        route = []
        meters = 0
        index = routing.Start(vehicle)
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                route.append(stop_ids[node - 1])
            next_index = solution.Value(routing.NextVar(index))
            meters += matrix[node][manager.IndexToNode(next_index)]
            index = next_index
        routes[driver] = route
        distance_km[driver] = round(meters / 1000, 2)

    return {
        "status": "ok",
        "routes": routes,
        "distance_km": distance_km,
        "total_km": round(sum(distance_km.values()), 2),
    }


def check_plan(result: dict, max_stops: int = MAX_STOPS_PER_DRIVER, expected_stops: list[int] | None = None) -> list[str]:
    """Return rule violations as readable strings. An empty list means the plan is OK.

    If expected_stops is given, also check that each of them is delivered exactly once.
    """
    if result.get("status") != "ok":
        return [f"No valid plan: {result.get('reason', result.get('status'))}"]

    violations = []
    for driver, route in result["routes"].items():
        if len(route) > max_stops:
            violations.append(f"{driver} has {len(route)} stops (max is {max_stops}).")

    counts = Counter(s for route in result["routes"].values() for s in route)
    for stop_id, n in sorted(counts.items()):
        if n > 1:
            violations.append(f"Stop {stop_id} is assigned {n} times.")

    if expected_stops is not None:
        missing = sorted(set(expected_stops) - set(counts))
        extra = sorted(set(counts) - set(expected_stops))
        if missing:
            violations.append(f"Stops not assigned to anyone: {missing}.")
        if extra:
            violations.append(f"Plan includes stops that are not active: {extra}.")

    return violations
