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
  - department_scope: relevant YAML departments (e.g. ["ap_citizen360"])
  - query_type: "data_query" | "document_query" | "hybrid" | "greeting"
"""
import os
import asyncio
import json
import logging
from typing import Literal

logger = logging.getLogger("app")

IMPALA_HOST = os.getenv("IMPALA_HOST") or os.getenv("HIVE_HOST", "dl-dev-cl-fn01.datalake-dev.local")
IMPALA_PORT = os.getenv("IMPALA_PORT") or os.getenv("HIVE_PORT", "21050")

try:
    from production_logger import set_current_user
except ImportError:
    def set_current_user(u: Any) -> None:
        pass

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
        if state.get("username"):
            set_current_user(state["username"])
        t0 = time.perf_counter()
        messages = state.get("messages", [])
        last_msg = messages[-1] if messages else None
        tool_calls = getattr(last_msg, "tool_calls", None) or []
        
        # Log tool invocations & retrieval starts
        for tc in tool_calls:
            name = tc.get("name", "unknown")
            args = tc.get("args", {})
            if name == "execute_sql":
                sql_preview = (args.get("sql") or args.get("query") or "").strip().replace("\n", " ")
                if len(sql_preview) > 180:
                    sql_preview = sql_preview[:177] + "..."
                logger.info(f"⚙️  [TOOL INVOKE] execute_sql | Impala: {IMPALA_HOST}:{IMPALA_PORT} | SQL: {sql_preview}")
            elif name in ("retrive_schema_rag", "search_documents"):
                query = args.get("query", "")
                top_k = args.get("top_k", 6)
                logger.info(f"🔍 [RETRIEVAL START] {name} | Query: '{query}' | top_k={top_k}")
            elif name == "search_exact_fewshot":
                query = args.get("query", "")
                logger.info(f"🎯 [RETRIEVAL START] search_exact_fewshot | Query: '{query}'")
            elif name == "get_column_values":
                tbl = args.get("table", "")
                col = args.get("column", "")
                logger.info(f"⚙️  [TOOL INVOKE] get_column_values | Table: {tbl} | Column: {col}")
            else:
                args_str = json.dumps(args, default=str)
                if len(args_str) > 150:
                    args_str = args_str[:147] + "..."
                logger.info(f"⚙️  [TOOL INVOKE] {name} | Args: {args_str}")

        result = await _base_tool_node.ainvoke(state)
        duration_ms = (time.perf_counter() - t0) * 1000
        exec_time = state.get("exec_time", 0.0) + (duration_ms / 1000.0)

        # Log tool completion outcomes, row counts, and retrieval results
        new_msgs = result.get("messages", []) if isinstance(result, dict) else []
        for tm in new_msgs:
            tool_name = getattr(tm, "name", "") or "tool"
            raw_content = getattr(tm, "content", "")
            if isinstance(raw_content, list):
                raw_content = raw_content[0].get("text", "") if raw_content else ""

            if tool_name == "execute_sql":
                try:
                    payload = json.loads(raw_content)
                    if isinstance(payload, dict) and payload.get("status") == "error":
                        err_msg = payload.get("error_msg") or payload.get("error_type") or "SQL error"
                        logger.warning(f"⚠️ [TOOL ERROR] execute_sql | Impala: {IMPALA_HOST}:{IMPALA_PORT} | duration={duration_ms:.2f}ms | Error: {err_msg}")
                    else:
                        rows = payload if isinstance(payload, list) else payload.get("rows", []) if isinstance(payload, dict) else []
                        row_cnt = len(rows) if isinstance(rows, list) else 0
                        logger.info(f"✅ [TOOL COMPLETED] execute_sql | Impala: {IMPALA_HOST}:{IMPALA_PORT} | duration={duration_ms:.2f}ms | Rows returned: {row_cnt}")
                except Exception:
                    logger.info(f"✅ [TOOL COMPLETED] execute_sql | Impala: {IMPALA_HOST}:{IMPALA_PORT} | duration={duration_ms:.2f}ms")
            elif tool_name in ("retrive_schema_rag", "search_documents"):
                try:
                    payload = json.loads(raw_content)
                    cnt = len(payload) if isinstance(payload, list) else len(payload.get("results", [])) if isinstance(payload, dict) else 1
                    logger.info(f"🔍 [RETRIEVAL COMPLETED] {tool_name} | duration={duration_ms:.2f}ms | Retrieved {cnt} schema/doc match(es)")
                except Exception:
                    logger.info(f"🔍 [RETRIEVAL COMPLETED] {tool_name} | duration={duration_ms:.2f}ms")
            elif tool_name == "search_exact_fewshot":
                try:
                    payload = json.loads(raw_content)
                    match_found = bool(payload) and payload.get("status") != "not_found"
                    status_text = "Found exact match" if match_found else "No exact match"
                    logger.info(f"🎯 [RETRIEVAL COMPLETED] search_exact_fewshot | duration={duration_ms:.2f}ms | Status: {status_text}")
                except Exception:
                    logger.info(f"🎯 [RETRIEVAL COMPLETED] search_exact_fewshot | duration={duration_ms:.2f}ms")
            else:
                logger.info(f"✅ [TOOL COMPLETED] {tool_name} | duration={duration_ms:.2f}ms")

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
        ["initialize_node", "doc_search_node", "deterministic_search_node", "greeting_node", END],
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
