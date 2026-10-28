from data import ALL_DRIVERS, ALL_STOPS
from solver import check_plan, plan_routes


def test_three_drivers_assign_every_stop_once():
    result = plan_routes(ALL_DRIVERS, ALL_STOPS)
    assert result["status"] == "ok"
    assigned = [s for route in result["routes"].values() for s in route]
    assert sorted(assigned) == sorted(ALL_STOPS)
    assert result["total_km"] > 0


def test_no_driver_exceeds_six_stops():
    result = plan_routes(ALL_DRIVERS, ALL_STOPS)
    assert all(len(route) <= 6 for route in result["routes"].values())
    assert check_plan(result, expected_stops=list(ALL_STOPS)) == []


def test_two_drivers_take_six_stops_each():
    result = plan_routes(["Driver 1", "Driver 3"], ALL_STOPS)
    assert result["status"] == "ok"
    assert [len(r) for r in result["routes"].values()] == [6, 6]


def test_one_driver_for_twelve_stops_is_infeasible():
    result = plan_routes(["Driver 1"], ALL_STOPS)
    assert result["status"] == "infeasible"
    assert "12 stops" in result["reason"]


def test_empty_inputs_return_clear_status():
    assert plan_routes([], ALL_STOPS)["status"] == "no_drivers"
    assert plan_routes(ALL_DRIVERS, {})["status"] == "no_stops"


def test_check_plan_flags_violations():
    bad = {
        "status": "ok",
        "routes": {"Driver 1": [1, 2, 3, 4, 5, 6, 7], "Driver 2": [7]},
        "distance_km": {},
        "total_km": 0,
    }
    violations = check_plan(bad, expected_stops=[1, 2, 3, 4, 5, 6, 7, 8])
    assert any("Driver 1 has 7 stops" in v for v in violations)
    assert any("Stop 7 is assigned 2 times" in v for v in violations)
    assert any("[8]" in v for v in violations)
