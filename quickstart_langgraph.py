"""
LangGraph Quickstart — Adapted for HOA Audit Swarm

This is the official LangGraph quickstart tutorial adapted to run locally.
It demonstrates the core concepts you'll use in the real swarm:

1. StateGraph — defining a graph of nodes and edges
2. Nodes — functions that process state  
3. Conditional Edges — routing logic between nodes
4. Tool Calling — LLM decides which tools to invoke
5. State Management — typed state that flows through the graph

Run this FIRST to verify your environment is working:
    python quickstart_langgraph.py

Once this works, you understand the fundamentals for building
the HOA Audit Swarm (Triage Router → Extractors → Auditor → Report).
"""

import os
import operator
from typing import Literal
from typing_extensions import TypedDict, Annotated
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import (
    AnyMessage,
    SystemMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, START, END

# ──────────────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────────────

load_dotenv()

# Verify API key is set
if not os.getenv("OPENAI_API_KEY"):
    print("❌ ERROR: OPENAI_API_KEY not set in .env file")
    print("   Copy .env.example to .env and add your key")
    exit(1)

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# ──────────────────────────────────────────────────────────────────────
# Step 1: Define Tools
# These are simple math tools for the tutorial.
# In the real swarm, tools will be: parse_pdf, extract_invoice, etc.
# ──────────────────────────────────────────────────────────────────────

@tool
def multiply(a: int, b: int) -> int:
    """Multiply a and b.

    Args:
        a: First int
        b: Second int
    """
    return a * b


@tool
def add(a: int, b: int) -> int:
    """Add a and b.

    Args:
        a: First int
        b: Second int
    """
    return a + b


@tool
def divide(a: int, b: int) -> float:
    """Divide a by b.

    Args:
        a: First int
        b: Second int
    """
    return a / b


# Register tools
tools = [add, multiply, divide]
tools_by_name = {t.name: t for t in tools}
model_with_tools = model.bind_tools(tools)


# ──────────────────────────────────────────────────────────────────────
# Step 2: Define State
# This is the typed state that flows through the graph.
# In the real swarm, state will contain: pages, invoices, audit_result
# ──────────────────────────────────────────────────────────────────────

class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


# ──────────────────────────────────────────────────────────────────────
# Step 3: Define Nodes
# Each node is a function that takes state and returns state updates.
# In the real swarm: triage_router(), invoice_extractor(), auditor()
# ──────────────────────────────────────────────────────────────────────

def llm_call(state: dict):
    """LLM decides whether to call a tool or respond to the user."""
    return {
        "messages": [
            model_with_tools.invoke(
                [
                    SystemMessage(
                        content="You are a helpful assistant tasked with "
                        "performing arithmetic on a set of inputs."
                    )
                ]
                + state["messages"]
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def tool_node(state: dict):
    """Execute the tool calls from the LLM response."""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool_fn = tools_by_name[tool_call["name"]]
        observation = tool_fn.invoke(tool_call["args"])
        result.append(
            ToolMessage(content=str(observation), tool_call_id=tool_call["id"])
        )
    return {"messages": result}


# ──────────────────────────────────────────────────────────────────────
# Step 4: Define Routing Logic
# This is the conditional edge — it decides where to go next.
# In the real swarm: "confidence >= 80%? → report" vs "< 80% → HITL veto"
# ──────────────────────────────────────────────────────────────────────

def should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
    """Route based on whether the LLM made a tool call."""
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tool_node"
    return END


# ──────────────────────────────────────────────────────────────────────
# Step 5: Build & Compile the Graph
# This is the same pattern you'll use for the full audit swarm.
# ──────────────────────────────────────────────────────────────────────

def build_agent():
    """Build and compile the LangGraph agent."""
    builder = StateGraph(MessagesState)

    # Add nodes
    builder.add_node("llm_call", llm_call)
    builder.add_node("tool_node", tool_node)

    # Add edges
    builder.add_edge(START, "llm_call")
    builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
    builder.add_edge("tool_node", "llm_call")

    # Compile
    return builder.compile()


# ──────────────────────────────────────────────────────────────────────
# Step 6: Run It
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 LangGraph Quickstart — HOA Audit Swarm Foundation")
    print("=" * 60)
    print()

    agent = build_agent()

    # Test queries that exercise different tools
    test_queries = [
        "Add 3 and 4.",
        "What is 12 multiplied by 7?",
        "Divide 100 by 3, then multiply the result by 2.",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"── Test {i}: {query}")
        print("-" * 40)

        result = agent.invoke(
            {"messages": [HumanMessage(content=query)], "llm_calls": 0}
        )

        # Print the conversation flow
        for msg in result["messages"]:
            if hasattr(msg, "content") and msg.content:
                role = msg.__class__.__name__.replace("Message", "")
                print(f"  [{role}] {msg.content}")

        print(f"  📊 Total LLM calls: {result['llm_calls']}")
        print()

    print("=" * 60)
    print("✅ LangGraph is working. You're ready to build the swarm.")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Add your OPENAI_API_KEY to .env")
    print("  2. Review src/schemas/financial.py (your data contracts)")
    print("  3. Start the LangChain Academy course")
    print("  4. Upload 5 HOA PDF pages to LlamaParse")
