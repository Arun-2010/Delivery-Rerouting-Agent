# CLAUDE.md

## Project

**Mini Delivery Rerouting Agent**: a small portfolio project for a Full-Stack Developer Intern (agentic AI) application at a last-mile delivery company.

A route planner (Google OR-Tools) plans deliveries for a few drivers. An AI agent (LangGraph) sits on top: the user describes a disruption in plain language ("Driver 2 is sick", "Remove order 7"), and the agent updates the data, re-plans the routes, checks the rules, and explains the new plan.

The point of the project is to show the difference between an optimizer and an agent: **the optimizer does the math, the agent decides what to ask it and what to do with the answer.**

## Scope (keep it small)

Target build time is 1–2 hours. Do not add anything outside this list unless I ask.

- 3 drivers, 12 delivery stops, 1 depot, all in Casablanca.
- Fake coordinates, generated with a fixed random seed so results are reproducible.
- Straight-line (haversine) distances. No maps API, no network calls except the LLM.
- One business rule: **a driver can have at most 6 stops.**
- In-memory data only. No database.
- A Streamlit chat UI (a terminal loop is an acceptable fallback).

Out of scope for now: databases, real maps, React, authentication, Docker, multi-agent setups.

## Stack

- Python 3.11+
- `ortools` for the vehicle routing problem
- `langgraph` + `langchain` for the agent (use `langgraph.prebuilt.create_react_agent` or LangChain's `create_agent`, whichever is simpler with the installed versions)
- `langchain-google-genai` (Gemini) for the model
- `streamlit` for the UI
- `python-dotenv` for config

Install:

```bash
pip install ortools langgraph langchain langchain-google-genai streamlit python-dotenv pytest
```

## Config

Secrets go in `.env` (never commit it). Provide `.env.example`:

```
GEMINI_API_KEY=your-key-here
MODEL_NAME=your-model-name
```

Read the model name from `MODEL_NAME`; do not hardcode a model.

## File structure

```
.
├── CLAUDE.md
├── README.md
├── .env.example
├── .gitignore          # includes .env, __pycache__, .venv
├── requirements.txt
├── data.py             # depot, drivers, stops, state helpers
├── solver.py           # plan_routes() using OR-Tools + check_plan()
├── tools.py            # agent tools wrapping data.py and solver.py
├── agent.py            # LangGraph agent + system prompt
├── app.py              # Streamlit chat UI
└── tests/
    ├── test_solver.py
    └── test_tools.py
```

## Module details

### data.py
- Depot at Casablanca center: `(33.5731, -7.5898)`.
- 12 stops with ids `1..12`, random points within ~8 km of the depot, `random.seed(42)`.
- 3 drivers: `"Driver 1"`, `"Driver 2"`, `"Driver 3"`.
- Keep state in a simple `State` dataclass (active drivers, active stops) with a `reset()` function so the UI can start over.
- `haversine_km(a, b)` helper.

### solver.py
- `plan_routes(drivers, stops, max_stops=6) -> dict`
  - Build a distance matrix in **integer meters** (OR-Tools needs integers).
  - Each vehicle starts and ends at the depot.
  - Add a count dimension so each driver visits at most `max_stops` stops (hard limit).
  - Use `PATH_CHEAPEST_ARC` first solution plus a short time limit (2 seconds) with guided local search.
  - Return `{"status": "ok", "routes": {driver: [stop_ids]}, "distance_km": {driver: float}, "total_km": float}`.
  - If there is no feasible solution (e.g. 1 driver left for 12 stops), return `{"status": "infeasible", "reason": "..."}` with a plain-English reason. Never raise for this case.
  - If there are zero drivers or zero stops, return a clear status instead of calling OR-Tools.
- `check_plan(result, max_stops=6) -> list[str]`: returns rule violations as readable strings (empty list means OK). Keep this separate so the agent can call it explicitly.

### tools.py
Wrap state changes as LangChain tools (`@tool` decorator) with clear docstrings, since the docstrings are what the model reads:

- `list_status()`: show active drivers and stops.
- `remove_driver(name: str)`: mark a driver unavailable. Error message if the name doesn't exist.
- `remove_stop(stop_id: int)`: cancel a delivery. Error message if the id doesn't exist.
- `plan_routes_tool()`: run the solver on current state and return a readable summary.
- `check_plan_tool()`: run `check_plan` on the latest plan.

Tools return short strings, not raw objects. Tools never raise on bad input; they return an error string the agent can react to.

### agent.py
- `build_agent()` returns the compiled agent with the tools above.
- System prompt, roughly:
  > You are a dispatch assistant for a delivery team. When the user reports a disruption, update the data with the tools, re-plan the routes, check the rules, and explain the new plan briefly: which driver takes which stops and total distance. If the plan is infeasible or breaks a rule, say so plainly and suggest options (e.g. bring a driver back, postpone stops). Never invent stops or drivers.
- Cap the agent loop (e.g. `recursion_limit=15`) so it can't loop forever.

### app.py
- Streamlit chat with `st.chat_input` / `st.chat_message`.
- Keep the agent, conversation, and data state in `st.session_state`.
- Sidebar: current routes as a small table per driver, total km, and a "Reset" button.
- Optional if time allows: show which tools the agent called for each answer in an expander. This is a good demo of "agentic" behavior.

## Build order

Build and test one piece at a time. Do not generate everything at once.

1. `data.py` → quick print check.
2. `solver.py` → `pytest tests/test_solver.py` must pass before moving on.
3. `tools.py` → `pytest tests/test_tools.py`.
4. `agent.py` → test in a small `if __name__ == "__main__":` loop in the terminal.
5. `app.py` → `streamlit run app.py`.
6. `README.md`.

## Tests

Keep tests fast and offline (no LLM calls in tests).

- Solver: all stops are assigned exactly once with 3 drivers; no driver exceeds 6 stops; 1 driver + 12 stops returns `"infeasible"` instead of crashing; empty inputs return a clear status.
- Tools: removing an unknown driver/stop returns an error string; removing a valid one changes state.

Run: `pytest -q`

## Commands

```bash
pytest -q              # run tests
python agent.py        # terminal chat with the agent
streamlit run app.py   # web chat UI
```

## Code style

- Simple, readable code over clever code. I need to explain every line in an interview.
- Type hints on public functions, short docstrings.
- No global mutable state outside `data.py`'s state object.
- Small functions; comment only where the logic isn't obvious (mainly the OR-Tools setup).

## Demo scenarios (use these to verify and for the README)

1. "Show me today's plan." → 3 drivers, 12 stops, no violations.
2. "Driver 2 is sick." → re-plan with 2 drivers, 6 stops each, no violations.
3. "Driver 3 is also out." → infeasible; the agent explains and suggests options.
4. "Cancel order 7 and order 9." → re-plan with fewer stops.

## README should include

- One-paragraph description and the "optimizer vs. agent" idea.
- Screenshot or GIF of the Streamlit chat.
- Setup and run commands.
- The four demo scenarios.
- A short "What I'd add next" list: real road distances (OSRM), time windows, a database, a human approval step before sending plans to drivers, an eval suite of disruption scenarios.