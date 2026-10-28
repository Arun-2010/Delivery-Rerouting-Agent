import pytest

import data
from tools import check_plan_tool, list_status, plan_routes_tool, remove_driver, remove_stop


@pytest.fixture(autouse=True)
def fresh_state():
    data.reset()
    yield
    data.reset()


def test_remove_unknown_driver_returns_error():
    assert remove_driver.invoke({"name": "Driver 9"}).startswith("Error")
    assert len(data.state.drivers) == 3


def test_remove_valid_driver_changes_state():
    message = remove_driver.invoke({"name": "driver 2"})
    assert "Driver 2 is now unavailable" in message
    assert data.state.drivers == ["Driver 1", "Driver 3"]


def test_remove_driver_twice_returns_error():
    remove_driver.invoke({"name": "Driver 2"})
    assert remove_driver.invoke({"name": "Driver 2"}).startswith("Error")


def test_remove_unknown_stop_returns_error():
    assert remove_stop.invoke({"stop_id": 99}).startswith("Error")
    assert len(data.state.stops) == 12


def test_remove_valid_stop_changes_state():
    remove_stop.invoke({"stop_id": 7})
    assert 7 not in data.state.stops
    assert len(data.state.stops) == 11


def test_check_without_plan_returns_error():
    assert check_plan_tool.invoke({}).startswith("Error")


def test_plan_then_check_is_ok():
    assert "Total distance" in plan_routes_tool.invoke({})
    assert check_plan_tool.invoke({}).startswith("OK")


def test_removing_a_driver_clears_the_plan():
    plan_routes_tool.invoke({})
    remove_driver.invoke({"name": "Driver 1"})
    assert data.state.last_plan is None
    assert "no (call plan_routes_tool)" in list_status.invoke({})


def test_one_driver_left_is_infeasible():
    remove_driver.invoke({"name": "Driver 1"})
    remove_driver.invoke({"name": "Driver 2"})
    assert "infeasible" in plan_routes_tool.invoke({})
    assert "No valid plan" in check_plan_tool.invoke({})
