"""
agent.py
--------
Constructs and compiles the LangGraph agent.

Graph flow:
  START → intent_node → initialize_node → tool_node → llm_node ↔ tool_node → verify_node → END
                                                                      ↓ (RETRY)
                                                                   llm_node (re-generate SQL)

intent_node classifies the user query and enriches state with:
  - intent: classified label (e.g. "student_risk_list")
  - department_scope: relevant YAML departments (e.g. ["school", "canonicalmodel"])
  - entities: extracted district, year, grade, social_category

initialize_node uses intent + entities to build an enriched RAG query.
"""
import asyncio
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from my_agent.utils.nodes import (
    build_tool_node, initialize_node, intent_node, llm_node, verify_node,
    route_node, doc_search_node, synthesize_node, greeting_node,
    deterministic_search_node, eval_fast_path_node, summarization_node
)
from my_agent.utils.state import AgentState
from my_agent.utils.tools import cleanup_tools, init_tools


def should_continue(state: AgentState) -> Literal["tool_node", "verify_node", "__end__"]:
    """
    After llm_node:
    - If the LLM emitted tool calls → run the tools.
    - If verified is True (verify_node already confirmed the answer) → stop.
    - Otherwise → stop (no tool calls and not yet verified means a plain answer).
    """
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tool_node"
    return END


def after_tool_node(state: AgentState) -> Literal["verify_node", "summarization_node", "llm_node", "synthesize_node", "eval_fast_path_node"]:
    """
    After tool_node executes:
    - If the tool was search_exact_fewshot → go to eval_fast_path_node.
    - If the tool was execute_sql:
        - SUCCESS → summarization_node directly (no verify needed, results are real data).
        - FAILURE → verify_node for targeted RAG re-retrieval and SQL rewrite.
    - If the tool was search_documents → go to synthesize_node.
    - Otherwise (schema retrieval) → go back to llm_node to generate SQL.
    """
    last_ai_message = None
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage) or getattr(msg, "__class__", None).__name__ == "AIMessage":
            last_ai_message = msg
            break

    if last_ai_message and getattr(last_ai_message, "tool_calls", None):
        tool_names = [tc["name"] for tc in last_ai_message.tool_calls]
        if "search_exact_fewshot" in tool_names:
            return "eval_fast_path_node"
        if "execute_sql" in tool_names:
            # Peek at the most recent ToolMessage to check execution outcome.
            # execute_sql returns {"status": "error", ...} on failure; anything
            # else (columns + rows) means the query ran successfully.
            for msg in reversed(state.get("messages", [])):
                if getattr(msg, "type", None) == "tool" or msg.__class__.__name__ == "ToolMessage":
                    try:
                        import json as _json
                        content = msg.content
                        if isinstance(content, list):
                            # Some ToolMessage implementations wrap content in a list
                            content = content[0].get("text", "") if content else ""
                        payload = _json.loads(content)
                        if payload.get("status") == "error":
                            return "verify_node"   # SQL failed → error recovery loop
                        return "summarization_node"  # SQL succeeded → summarize directly
                    except Exception:
                        break  # Can't parse → fall back to verify_node below
            return "verify_node"
        if "search_documents" in tool_names:
            return "synthesize_node"

    return "llm_node"



def after_eval_fast_path(state: AgentState) -> Literal["tool_node", "initialize_node"]:
    if state.get("fast_sql"):
        return "tool_node"
    return "initialize_node"


def after_verify_node(state: AgentState) -> Literal["llm_node", "tool_node", "summarization_node"]:
    """
    After verify_node:
    - CORRECT (verified=True) → summarization_node to summarize the result.
    - RETRY with forced tool call (verified=False, last message has tool_calls) →
        go to tool_node to execute the pending tool (e.g. forced RAG re-retrieval).
    - RETRY plain correction (verified=False) → loop back to llm_node.
    """
    if state.get("verified", False):
        return "summarization_node"
    # If verify_node emitted a forced tool call (e.g. RAG re-retrieval on SQL error),
    # route directly to tool_node to execute it rather than passing through llm_node.
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tool_node"
    return "llm_node"


async def build_graph():
    """
    Initialises MCP tools, builds the graph, compiles, and returns it.
    Call once at application startup.
    """
    await init_tools()
    _base_tool_node = build_tool_node()
    
    import time
    async def wrapped_tool_node(state: AgentState):
        t0 = time.perf_counter()
        result = await _base_tool_node.ainvoke(state)
        exec_time = state.get("exec_time", 0.0) + (time.perf_counter() - t0)
        if isinstance(result, dict):
            result["exec_time"] = exec_time
        return result

    builder = StateGraph(AgentState)
    builder.add_node("intent_node",      intent_node)       # NEW — classifies intent
    builder.add_node("initialize_node",  initialize_node)
    builder.add_node("llm_node",         llm_node)
    builder.add_node("tool_node",        wrapped_tool_node)
    builder.add_node("verify_node",      verify_node)
    builder.add_node("doc_search_node",  doc_search_node)
    builder.add_node("synthesize_node",  synthesize_node)
    builder.add_node("greeting_node",    greeting_node)
    builder.add_node("deterministic_search_node", deterministic_search_node)
    builder.add_node("eval_fast_path_node",       eval_fast_path_node)
    builder.add_node("summarization_node",        summarization_node)

    # Intent classification → route_node
    builder.add_edge(START,           "intent_node")
    
    builder.add_conditional_edges(
        "intent_node",
        route_node,
        ["initialize_node", "doc_search_node", "deterministic_search_node", "greeting_node"],
    )
    
    builder.add_edge("initialize_node", "tool_node")
    builder.add_edge("doc_search_node", "tool_node")
    builder.add_edge("deterministic_search_node", "tool_node")
    builder.add_edge("greeting_node", END)

    # llm_node → tool_node (tool call) or END (plain answer)
    builder.add_conditional_edges(
        "llm_node",
        should_continue,
        ["tool_node", END],
    )

    # tool_node goes to verify_node, summarization_node (fast path), synthesize_node,
    # eval_fast_path_node, or llm_node
    builder.add_conditional_edges(
        "tool_node",
        after_tool_node,
        ["verify_node", "summarization_node", "llm_node", "synthesize_node", "eval_fast_path_node"],
    )

    # eval_fast_path_node goes to tool_node (if match) or initialize_node (fallback)
    builder.add_conditional_edges(
        "eval_fast_path_node",
        after_eval_fast_path,
        ["tool_node", "initialize_node"],
    )

    # verify_node → summarization_node (correct) or llm_node (retry plain) or tool_node (retry with forced tool call)
    builder.add_conditional_edges(
        "verify_node",
        after_verify_node,
        ["llm_node", "tool_node", "summarization_node"],
    )
    
    builder.add_edge("synthesize_node", END)
    builder.add_edge("summarization_node", END)

    graph = builder.compile()
    print("Agent graph compiled successfully.")
    return graph


async def main():
    graph = await build_graph()
    user_query = "List dropout students from AAY ration-card households in Anantapur in 2025-26."
    result = await graph.ainvoke(
        {
            "user_query": user_query,
            "messages": [HumanMessage(content=user_query)],
            "retrieved_context": [],
            "llm_calls": 0,
            "rag_calls": 0,
            "verify_calls": 0,
            "verified": False,
            # intent_node will populate these at runtime:
            "intent": None,
            "department_scope": None,
            "entities": None,
        }
    )

    print("\n" + "=" * 60)
    print("CONVERSATION TRACE")
    print("=" * 60)
    for message in result["messages"]:
        message.pretty_print()
    print(f"\nLLM calls made:    {result['llm_calls']}")
    print(f"Verify loops run:  {result['verify_calls']}")
    print(f"Verified:          {result['verified']}")
    print(f"Intent:            {result.get('intent', 'N/A')}")
    print(f"Department scope:  {result.get('department_scope', 'N/A')}")
    print(f"Entities:          {result.get('entities', 'N/A')}")

    await cleanup_tools()


if __name__ == "__main__":
    asyncio.run(main())
