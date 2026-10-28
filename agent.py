"""The dispatch agent: an LLM that decides which tools to call, built with LangGraph."""

import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from tools import TOOLS

load_dotenv()

# Each model call and each tool call is one step; 15 is plenty for one request but stops runaway loops.
RECURSION_LIMIT = 15

SYSTEM_PROMPT = """You are a dispatch assistant for a delivery team in Casablanca.

When the user reports a disruption, update the data with the tools, re-plan the routes, \
check the rules, and explain the new plan briefly: which driver takes which stops and the total distance.
If the plan is infeasible or breaks a rule, say so plainly and suggest options \
(e.g. bring a driver back, postpone stops).
Never invent stops or drivers. Only use ids and names the tools tell you about.
"Order N" means stop N. Keep answers short."""


def build_agent(model: BaseChatModel | None = None):
    """Return the compiled agent. Uses MODEL_NAME from .env unless a model is passed in."""
    if model is None:
        model_name = os.getenv("MODEL_NAME")
        if not model_name:
            raise RuntimeError("Set MODEL_NAME in your .env file (see .env.example).")
        # Reads the API key from GEMINI_API_KEY (or GOOGLE_API_KEY).
        model = ChatGoogleGenerativeAI(model=model_name, temperature=0)
    agent = create_agent(model, TOOLS, system_prompt=SYSTEM_PROMPT)
    return agent.with_config({"recursion_limit": RECURSION_LIMIT})


if __name__ == "__main__":
    agent = build_agent()
    messages = []
    print("Dispatch assistant. Describe a disruption, or type 'quit'.")
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in {"quit", "exit"}:
            break
        if not user_input:
            continue
        messages.append(HumanMessage(user_input))
        result = agent.invoke({"messages": messages})
        messages = result["messages"]
        print(f"\nAgent: {messages[-1].text}")
