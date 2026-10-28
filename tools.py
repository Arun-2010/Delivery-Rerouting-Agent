"""Agent tools. Each one wraps data.py or solver.py and returns a short string.

The docstrings are what the model reads to decide which tool to call.
Tools never raise on bad input; they return an error string instead.
"""

from langchain_core.tools import tool

import data
from solver import check_plan, plan_routes


def _find_driver(name: str) -> str | None:
    """Match a driver name case-insensitively, e.g. 'driver 2' -> 'Driver 2'."""
    for driver in data.ALL_DRIVERS:
        if driver.lower() == name.strip().lower():
            return driver
    return None


def format_plan(result: dict) -> str:
    """Readable summary of a plan_routes() result."""
    if result["status"] != "ok":
        return f"Plan status: {result['status']}. {result['reason']}"
    lines = []
    for driver, route in result["routes"].items():
        if route:
            stops = " -> ".join(str(s) for s in route)
            lines.append(f"{driver}: depot -> {stops} -> depot ({len(route)} stops, {result['distance_km'][driver]} km)")
        else:
            lines.append(f"{driver}: no stops (not needed)")
    lines.append(f"Total distance: {result['total_km']} km")
    return "\n".join(lines)


@tool
def list_status() -> str:
    """Show which drivers are available, which delivery stops are still active, and whether a plan exists."""
    unavailable = [d for d in data.ALL_DRIVERS if d not in data.state.drivers]
    cancelled = [s for s in data.ALL_STOPS if s not in data.state.stops]
    plan = "yes" if data.state.last_plan else "no (call plan_routes_tool)"
    return (
        f"Available drivers: {', '.join(data.state.drivers) or 'none'}\n"
        f"Unavailable drivers: {', '.join(unavailable) or 'none'}\n"
        f"Active stops ({len(data.state.stops)}): {sorted(data.state.stops)}\n"
        f"Cancelled stops: {cancelled or 'none'}\n"
        f"Max stops per driver: {data.MAX_STOPS_PER_DRIVER}\n"
        f"Current plan: {plan}"
    )


@tool
def remove_driver(name: str) -> str:
    """Mark a driver as unavailable (sick, vehicle broken, etc.). Use the exact name, e.g. "Driver 2".

    This clears the current plan, so call plan_routes_tool afterwards.
    """
    driver = _find_driver(name)
    if driver is None:
        return f"Error: no driver named '{name}'. Known drivers: {', '.join(data.ALL_DRIVERS)}."
    if driver not in data.state.drivers:
        return f"Error: {driver} is already unavailable."
    data.state.drivers.remove(driver)
    data.state.last_plan = None
    return f"{driver} is now unavailable. Available drivers: {', '.join(data.state.drivers) or 'none'}."


@tool
def remove_stop(stop_id: int) -> str:
    """Cancel a delivery stop (order) by its id, e.g. 7 for "order 7".

    This clears the current plan, so call plan_routes_tool afterwards.
    """
    if stop_id not in data.ALL_STOPS:
        return f"Error: no stop with id {stop_id}. Valid ids are 1 to {len(data.ALL_STOPS)}."
    if stop_id not in data.state.stops:
        return f"Error: stop {stop_id} is already cancelled."
    del data.state.stops[stop_id]
    data.state.last_plan = None
    return f"Stop {stop_id} cancelled. {len(data.state.stops)} stops remain."


@tool
def plan_routes_tool() -> str:
    """Re-plan routes for the available drivers and active stops, minimizing total distance.

    Returns each driver's stops in order and the distances, or explains why no plan is possible.
    """
    result = plan_routes(data.state.drivers, data.state.stops, data.MAX_STOPS_PER_DRIVER)
    data.state.last_plan = result
    return format_plan(result)


@tool
def check_plan_tool() -> str:
    """Check the latest plan against the business rules (max stops per driver, every active stop delivered once)."""
    if data.state.last_plan is None:
        return "Error: there is no current plan. Call plan_routes_tool first."
    violations = check_plan(data.state.last_plan, data.MAX_STOPS_PER_DRIVER, list(data.state.stops))
    if not violations:
        return "OK: the plan follows all rules."
    return "Rule violations:\n" + "\n".join(f"- {v}" for v in violations)


TOOLS = [list_status, remove_driver, remove_stop, plan_routes_tool, check_plan_tool]
