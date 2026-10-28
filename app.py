"""Streamlit chat UI for the dispatch agent. Run with: streamlit run app.py"""

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError

import data
from agent import build_agent
from solver import plan_routes

EXAMPLES = ["Show me today's plan.", "Driver 2 is sick.", "Driver 3 is also out.", "Cancel order 7 and order 9."]


def start_over() -> None:
    """Fresh data, a starting plan for the sidebar, and an empty conversation."""
    data.reset()
    data.state.last_plan = plan_routes(data.state.drivers, data.state.stops, data.MAX_STOPS_PER_DRIVER)
    st.session_state.messages = []  # LangChain messages sent to the agent
    st.session_state.chat = []  # what the UI shows: role, content, tool steps


def tool_steps(new_messages: list) -> list[dict]:
    """Pair each tool call the agent made with the tool's output."""
    outputs = {m.tool_call_id: m.text for m in new_messages if isinstance(m, ToolMessage)}
    steps = []
    for m in new_messages:
        if isinstance(m, AIMessage):
            for call in m.tool_calls:
                steps.append({"tool": call["name"], "args": call["args"], "output": outputs.get(call["id"], "")})
    return steps


def show_steps(steps: list[dict]) -> None:
    if not steps:
        return
    with st.expander(f"Tools called ({len(steps)})"):
        for i, step in enumerate(steps, 1):
            st.markdown(f"**{i}. `{step['tool']}`** `{step['args']}`")
            st.code(step["output"], language=None)


def show_sidebar() -> None:
    st.sidebar.header("Current routes")
    plan = data.state.last_plan
    if plan is None:
        st.sidebar.info("Plan is out of date. Ask the agent to re-plan.")
    elif plan["status"] != "ok":
        st.sidebar.error(plan["reason"])
    else:
        rows = []
        for driver in data.ALL_DRIVERS:
            route = plan["routes"].get(driver)
            if route is None:
                rows.append({"Driver": driver, "Stops": "unavailable", "#": 0, "Km": 0.0})
            else:
                rows.append({"Driver": driver, "Stops": " → ".join(map(str, route)) or "-", "#": len(route), "Km": plan["distance_km"][driver]})
        st.sidebar.dataframe(rows, hide_index=True)
        st.sidebar.metric("Total distance", f"{plan['total_km']} km")

    cancelled = [s for s in data.ALL_STOPS if s not in data.state.stops]
    st.sidebar.caption(f"Active stops: {len(data.state.stops)} · Cancelled: {cancelled or 'none'}")
    if st.sidebar.button("Reset"):
        start_over()
        st.rerun()


st.set_page_config(page_title="Delivery Rerouting Agent", page_icon="🚚")
st.title("🚚 Delivery Rerouting Agent")
st.caption("Describe a disruption in plain language. Try: " + " · ".join(f"“{e}”" for e in EXAMPLES))

# A new browser session starts from fresh data (single-user demo: data lives in data.state).
if "chat" not in st.session_state:
    start_over()
if "agent" not in st.session_state:
    try:
        st.session_state.agent = build_agent()
    except Exception as e:
        st.error(f"Could not start the agent: {e}")
        st.stop()

for entry in st.session_state.chat:
    with st.chat_message(entry["role"]):
        st.markdown(entry["content"])
        show_steps(entry.get("steps", []))

if prompt := st.chat_input("e.g. Driver 2 is sick"):
    st.session_state.chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        history = st.session_state.messages + [HumanMessage(prompt)]
        steps = []
        try:
            with st.spinner("Thinking..."):
                result = st.session_state.agent.invoke({"messages": history})
            st.session_state.messages = result["messages"]
            steps = tool_steps(result["messages"][len(history):])
            answer = result["messages"][-1].text
        except GraphRecursionError:
            answer = "I took too many steps without finishing, so I stopped. Please try rephrasing."
        except Exception as e:
            answer = f"Something went wrong talking to the model: {e}"
        st.markdown(answer)
        show_steps(steps)
    st.session_state.chat.append({"role": "assistant", "content": answer, "steps": steps})

# Drawn last so it shows the plan after this turn's tool calls.
show_sidebar()
