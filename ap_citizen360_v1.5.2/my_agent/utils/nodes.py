"""
nodes.py
--------
LangGraph node functions for the SQL assistant.

The LLM decides whether to call schema RAG (`retrive_schema_rag`), SQL execution
(`execute_sql`), or answer directly. There is no deterministic retrieval node in
the graph.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.prebuilt import ToolNode

from my_agent.utils import tools as tool_registry
from my_agent.utils.state import AgentState

logger = logging.getLogger("agent.nodes")

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3.5:9b")
_REASONING = os.getenv("OLLAMA_REASONING", "true").strip().lower() in ("true", "1", "yes")
print(f"ChatOllama model: {_CHAT_MODEL}  |  thinking={'on' if _REASONING else 'off'}")

_base_model = ChatOllama(
    model=_CHAT_MODEL,
    temperature=0,
    reasoning=_REASONING,
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "4096")),
    num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "512")),
)
_model_with_tools = None

_summarize_model = ChatOllama(
    model=_CHAT_MODEL,
    temperature=0,
    reasoning=False,
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    num_ctx=int(os.getenv("OLLAMA_SUMMARIZE_NUM_CTX", "2048")),
    num_predict=int(os.getenv("OLLAMA_SUMMARIZE_NUM_PREDICT", "128")),
)

_doc_synthesize_model = ChatOllama(
    model=_CHAT_MODEL,
    temperature=0,
    reasoning=False,
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    num_ctx=int(os.getenv("OLLAMA_DOC_NUM_CTX", "4096")),
    num_predict=int(os.getenv("OLLAMA_DOC_NUM_PREDICT", "256")),
)

_HIVE_ENABLED = os.getenv("HIVE_MCP_ENABLED", "false").strip().lower() in ("true", "1", "yes")
_RAG_TOP_K = int(os.getenv("RAG_TOP_K", "15"))

if _HIVE_ENABLED:
    SYSTEM_PROMPT = """You are a data and document assistant for the ap_citizen360 data model.

Available tools:
- retrive_schema_rag: retrieve curated table DDL, key joins, columns, and rules when you need schema context.
- execute_sql: execute read-only Hive SQL SELECT queries against the database.
- search_documents: search policy documents, circulars, and guidelines (PDF/DOCX/TXT) for rules, procedures, or explanations.
- get_column_values: look up known distinct values for a specific table column (e.g. district names, academic years, school management types). Use this INSTEAD of running SELECT DISTINCT queries.

STRICT RULES — follow every rule without exception:
1. For ANY question about counts, totals, lists, averages, rates, trends, or data values — you MUST call execute_sql.
2. ALWAYS call retrive_schema_rag FIRST before writing any SQL. Use ONLY the exact table names and column names returned by retrive_schema_rag — never invent or guess names. If a table you need is not in the retrieved results, call retrive_schema_rag again with a more specific query describing what that table contains.
3. If execute_sql fails with a table-not-found or column-not-found error, do NOT retry the same SQL. Call retrive_schema_rag again with a targeted query to find the correct table/column names, then rewrite the SQL.
4. NEVER describe DDL or schema to the user — always run execute_sql and report the actual data.
5. NEVER answer without calling execute_sql for data questions.
6. After execute_sql returns rows, summarize the result in plain language.
7. The database is Hive/Impala - use Hive/Spark-compatible SQL only. Always prefix table names with the database (e.g. `ap_citizen360.table_name`).
8. NEVER guess, invent, or assume any table names, column names, or join relations. If you lack the DDL context or column definitions for a table, you MUST call retrive_schema_rag to retrieve it. Do not attempt to guess or invent columns/tables under any circumstances.
9. BEFORE using any filter value in a WHERE clause (like district name, status, or academic year), you MUST verify the exact spelling by calling get_column_values. Do NOT blindly trust the user's spelling and do NOT invent your own. Always use the closest matching valid value returned by the tool.
"""
else:
    SYSTEM_PROMPT = """You are a data and document assistant for the ap_citizen360 data model.

Available tools:
- retrive_schema_rag: retrieve curated table DDL, key joins, columns, and rules when you need schema context.
- execute_sql: execute read-only SQLite SELECT queries against the sample database.
- search_documents: search policy documents, circulars, and guidelines (PDF/DOCX/TXT) for rules, procedures, or explanations.
- get_column_values: look up known distinct values for a specific table column (e.g. district names, academic years, school management types). Use this INSTEAD of running SELECT DISTINCT queries.

STRICT RULES — follow every rule without exception:
1. For ANY question about counts, totals, lists, averages, rates, trends, or data values — you MUST call execute_sql.
2. ALWAYS call retrive_schema_rag FIRST before writing any SQL. Use ONLY the exact table names and column names returned by retrive_schema_rag. NEVER guess, invent, or assume any table names, column names, or join relations. If you lack the DDL context or column definitions for a table, you MUST call retrive_schema_rag to retrieve it. Do not attempt to guess or invent columns/tables under any circumstances.
3. NEVER describe DDL or schema to the user — always run execute_sql and report the actual data.
4. NEVER answer without calling execute_sql for data questions.
5. After execute_sql returns rows, summarize the result in plain language.
6. The database is SQLite - use SQLite-compatible SQL only. All tables are in the main schema with no prefix (e.g. write `citizen_student` instead of `ap_citizen360.citizen_student`).
7. BEFORE using any filter value in a WHERE clause (like district name, status, or academic year), you MUST verify the exact spelling by calling get_column_values. Do NOT blindly trust the user's spelling and do NOT invent your own. Always use the closest matching valid value returned by the tool.
"""


def _get_model():
    global _model_with_tools
    if _model_with_tools is None:
        if not tool_registry.all_tools:
            raise RuntimeError(
                "Tools not loaded. Make sure init_tools() was awaited before compiling the graph."
            )
        _model_with_tools = _base_model.bind_tools(tool_registry.all_tools)
    return _model_with_tools


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.lower().replace("data base", "database"))


def _needs_data_tool(query: str) -> bool:
    q = _normalize_query(query)
    triggers = (
        "how many", "count", "number of", "total", "list", "show", "what is",
        "average", "avg", "percent", "rate", "trend", "chart", "pie", "bar",
        "heatmap", "student", "teacher", "gender", "district", "school",
        "attendance", "absent", "absence", "marks", "score", "risk", "scheme",
        "meal", "infrastructure", "database", "table",
    )
    return any(trigger in q for trigger in triggers)


def _tool_messages(messages: list, name: str | None = None) -> list:
    out = [
        m for m in messages
        if isinstance(m, ToolMessage) or getattr(m, "__class__", None).__name__ == "ToolMessage"
    ]
    if name:
        out = [m for m in out if getattr(m, "name", None) == name]
    return out


def _extract_tool_content(content: Any) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                return item
            if isinstance(item, dict) and item.get("type") == "text":
                return item.get("text")
    return str(content)


def _summarize_sql_result(user_query: str, tool_content: Any) -> str | None:
    text_content = _extract_tool_content(tool_content)
    if not text_content:
        return None
    try:
        payload = json.loads(text_content)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return None

    rows = payload.get("rows") or []
    columns = payload.get("columns") or []
    if not rows:
        return "The query ran successfully but returned no rows."

    q = _normalize_query(user_query)
    if len(rows) == 1 and len(columns) == 1:
        val = rows[0].get(columns[0])
        if re.search(r"how many|count|number of|total|average|avg", q):
            label = columns[0].replace("_", " ")
            return f"**{val:,}** ({label})." if isinstance(val, (int, float)) else f"**{val}** ({label})."

    if len(rows) <= 15 and columns:
        header = " | ".join(columns)
        body = "\n".join(
            " | ".join(str(row.get(column, "")) for column in columns)
            for row in rows[:15]
        )
        extra = ""
        if len(rows) < payload.get("row_count", len(rows)):
            extra = f"\n\n_Showing {len(rows)} of {payload.get('row_count', len(rows))} rows._"
        return f"**Query results:**\n\n{header}\n{body}{extra}"

    return (
        f"Query returned **{payload.get('row_count', len(rows))}** rows "
        f"({', '.join(columns[:6])}{'...' if len(columns) > 6 else ''})."
    )


def llm_node(state: AgentState) -> dict:
    """
    Invoke the LLM. The LLM may call schema retrieval, execute SQL, or answer.
    Retry guards nudge data questions back to tools if the model answers without
    a tool call, or if it called SQL with wrong columns then retrieved schema.
    """
    t0 = time.perf_counter()
    history = state.get("messages", [])
    if not history:
        history = [HumanMessage(content=state["user_query"])]

    # Hard cap on LLM calls to prevent infinite loops
    current_calls = state.get("llm_calls", 0)
    current_rag_calls = state.get("rag_calls", 0)
    max_llm_calls = int(os.getenv("MAX_LLM_CALLS", "25"))
    if current_calls >= max_llm_calls:
        logger.warning("llm_node: Max LLM call limit reached (%d). Ending conversation.", current_calls)

        # If a successful SQL result already exists in history, surface it so the
        # API can return a 200 instead of a 502.  This is the common case when
        # verify_node keeps requesting retries even though good data was found.
        successful_sql_msgs = [
            m for m in _tool_messages(history, "execute_sql")
            if _summarize_sql_result(state["user_query"], m.content) is not None
        ]
        if successful_sql_msgs:
            summary = _summarize_sql_result(state["user_query"], successful_sql_msgs[-1].content)
            logger.info("llm_node: returning best available SQL result after hitting call cap.")
            return {
                "messages": [AIMessage(content=summary or "Query executed successfully.")],
                "llm_calls": current_calls,
                "rag_calls": current_rag_calls,
                "verified": True,
                "gen_time": state.get("gen_time", 0.0) + (time.perf_counter() - t0),
            }

        # No successful result at all — collect the last SQL error for the hint.
        last_sql_error: str | None = None
        for m in reversed(_tool_messages(history, "execute_sql")):
            try:
                text_content = _extract_tool_content(m.content)
                if text_content:
                    err_payload = json.loads(text_content)
                    if err_payload.get("status") == "error":
                        last_sql_error = err_payload.get("error_msg") or err_payload.get("error_type")
                        break
            except (json.JSONDecodeError, TypeError, AttributeError):
                break

        error_hint = f" (Last error: {last_sql_error})" if last_sql_error else ""
        return {
            "messages": [AIMessage(content=f"I encountered multiple issues or errors while trying to query the database. Please try rephrasing your request.{error_hint}")],
            "llm_calls": current_calls,
            "rag_calls": current_rag_calls,
            "verified": True,
            "gen_time": state.get("gen_time", 0.0) + (time.perf_counter() - t0),
        }

    # If a successful SQL result already exists in history, summarise and stop —
    # BUT only if we are not currently in a verification retry cycle.
    # When verify_calls > 0 and verified is still False the verify_node sent us
    # back here to regenerate SQL, so we must NOT short-circuit.
    in_verify_retry = state.get("verify_calls", 0) > 0 and not state.get("verified", False)
    sql_results = _tool_messages(history, "execute_sql")
    if sql_results and not in_verify_retry:
        summary = _summarize_sql_result(state["user_query"], sql_results[-1].content)
        if summary:
            logger.info("llm_node: summarized SQL result in %.2fs", time.perf_counter() - t0)
            return {
                "messages": [AIMessage(content=summary)],
                "llm_calls": current_calls,
                "rag_calls": current_rag_calls,
                "gen_time": state.get("gen_time", 0.0) + (time.perf_counter() - t0),
            }

    system_message = SystemMessage(content=SYSTEM_PROMPT)
    messages_for_llm = [system_message] + history

    rag_results = _tool_messages(history, "retrive_schema_rag")
    if rag_results:
        # Schema context is already in history — nudge the LLM toward SQL.
        # The RAG result contains two clearly labelled sections:
        #   "REFERENCE SQL EXAMPLES" — use as a query pattern
        #   "SCHEMA DDLs"            — authoritative table/column names
        # The LLM must use ONLY table and column names from the SCHEMA DDLs section.
        # It may call retrive_schema_rag again if it needs schema for a different table.
        dialect_name = "Hive SQL" if _HIVE_ENABLED else "SQLite SQL"
        if current_rag_calls >= _MAX_RAG_CALLS:
            # RAG call budget exhausted — stop asking for more schema retrieval.
            # Force the LLM to write SQL with whatever schema is already in context.
            logger.warning(
                "llm_node: RAG call cap (%d) reached. Forcing SQL generation with existing schema context.",
                _MAX_RAG_CALLS,
            )
            messages_for_llm.append(SystemMessage(
                content=(
                    "You have already retrieved schema context multiple times. "
                    "Do NOT call retrive_schema_rag again. "
                    "Use ONLY the table and column names already present in the conversation above. "
                    f"Call execute_sql now with a valid {dialect_name} SELECT query."
                )
            ))
        else:
            messages_for_llm.append(SystemMessage(
                content=(
                    "The schema context above contains two sections:\n"
                    "1. REFERENCE SQL EXAMPLES — use these as a structural pattern for your query.\n"
                    "2. SCHEMA DDLs — these are the authoritative table and column names. "
                    "You MUST use ONLY the exact table names and column names from the SCHEMA DDLs section. "
                    "Do NOT guess, assume, or invent any column names, table names, or joins. "
                    "If a column or table you want to query is not present in the SCHEMA DDLs section, you must call retrive_schema_rag again to fetch the correct schema instead of guessing it. "
                    "Now call execute_sql with a correct {dialect} query."
                ).format(dialect=dialect_name)
            ))
    model = _get_model()
        
    response = model.invoke(messages_for_llm)
    llm_steps = 1

    # Retry 1: model answered without calling any tool at all.
    if (
        _needs_data_tool(state["user_query"])
        and not getattr(response, "tool_calls", None)
        and not _tool_messages(history)
    ):
        retry_hint = HumanMessage(
            content=(
                "This is a database question. You MUST call retrive_schema_rag first "
                "if you don't know the table, then call execute_sql. "
                "Do NOT answer without running SQL."
            )
        )
        response = _get_model().invoke(messages_for_llm + [retry_hint])
        llm_steps += 1

    # Retry 2: RAG was retrieved but there is still no SUCCESSFUL execute_sql.
    # Covers two cases:
    #   a) RAG called, SQL never attempted → nudge to run SQL now.
    #   b) SQL attempted with wrong columns (error), then RAG fetched schema →
    #      nudge to retry SQL using the retrieved column names.
    rag_results = _tool_messages(history, "retrive_schema_rag")
    successful_sql = [
        m for m in _tool_messages(history, "execute_sql")
        if _summarize_sql_result(state["user_query"], m.content) is not None
    ]

    # Collect the last SQL error message (if any) to include in the nudge.
    last_sql_error: str | None = None
    for m in reversed(_tool_messages(history, "execute_sql")):
        try:
            text_content = _extract_tool_content(m.content)
            if text_content:
                err_payload = json.loads(text_content)
                if err_payload.get("status") == "error":
                    last_sql_error = err_payload.get("error_msg") or err_payload.get("error_type")
                    break
        except (json.JSONDecodeError, TypeError, AttributeError):
            break

    if (
        rag_results
        and not successful_sql
        and not getattr(response, "tool_calls", None)
        and _needs_data_tool(state["user_query"])
    ):
        db_type = "Hive" if _HIVE_ENABLED else "SQLite"
        error_hint = (
            f" The previous SQL failed: {last_sql_error}."
            " Use the exact column names from the schema you just retrieved."
            if last_sql_error else ""
        )
        sql_nudge = HumanMessage(
            content=(
                f'The user asked: "{state["user_query"]}"\n\n'
                "You have already retrieved the schema context above."
                f"{error_hint} "
                f"Now call execute_sql with a valid {db_type} SELECT query "
                "using the exact column names shown in the schema. "
                "Do NOT describe the schema — call execute_sql right now."
            )
        )
        response = _get_model().invoke(messages_for_llm + [sql_nudge])
        llm_steps += 1

    # Count how many RAG tool calls the LLM emitted in this node turn
    rag_increment = sum(
        1 for tc in (getattr(response, "tool_calls", None) or [])
        if tc.get("name") == "retrive_schema_rag"
    )

    # ── HARD ENFORCEMENT: strip RAG tool calls when budget is exhausted ──────
    # Small models (e.g. 0.8B) often ignore the system-message nudge and keep
    # emitting retrive_schema_rag tool calls.  If the RAG cap has been reached,
    # we surgically remove those calls from the response so tool_node never
    # executes them.  This breaks the infinite RAG→llm→RAG loop.
    if current_rag_calls + rag_increment > _MAX_RAG_CALLS and getattr(response, "tool_calls", None):
        filtered_calls = [
            tc for tc in response.tool_calls
            if tc.get("name") != "retrive_schema_rag"
        ]
        if len(filtered_calls) != len(response.tool_calls):
            stripped = len(response.tool_calls) - len(filtered_calls)
            logger.warning(
                "llm_node: HARD CAP — stripped %d retrive_schema_rag call(s) from LLM response "
                "(rag_calls=%d, cap=%d)", stripped, current_rag_calls + rag_increment, _MAX_RAG_CALLS,
            )
            response.tool_calls = filtered_calls
            # If no tool calls remain, the LLM essentially produced a text-only
            # response.  If it also has no content, synthesise a fallback.
            if not response.tool_calls and not response.content:
                response.content = (
                    "I have the schema context. Let me write the SQL query now."
                )
            # Recalculate increment after stripping
            rag_increment = 0

    logger.info("llm_node: completed in %.2fs (rag_calls this turn: %d)", time.perf_counter() - t0, rag_increment)
    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + llm_steps,
        "rag_calls": current_rag_calls + rag_increment,
        "gen_time": state.get("gen_time", 0.0) + (time.perf_counter() - t0),
    }


def build_tool_node() -> ToolNode:
    """Returns a ToolNode bound to all MCP tools."""
    if not tool_registry.all_tools:
        raise RuntimeError("Tools not loaded before building tool node.")
    return ToolNode(tool_registry.all_tools)


# ---------------------------------------------------------------------------
# Verification node
# ---------------------------------------------------------------------------
_MAX_VERIFY_LOOPS = int(os.getenv("MAX_VERIFY_LOOPS", "10"))
_MAX_RAG_CALLS   = int(os.getenv("MAX_RAG_CALLS", "4"))

_VERIFY_PROMPT = """You are a strict SQL result verifier.

User question: {user_query}

SQL query that was executed:
{sql}

Query result (up to 20 rows shown):
{result_table}

Does this result correctly and completely answer the user's question?

Reply with EXACTLY one of:
  CORRECT: <one-sentence explanation of why the result is correct>
  RETRY: <one-sentence explanation of what is wrong and how to fix the SQL>

Do NOT output anything else."""


def _extract_sql_from_history(history: list) -> str:
    """Extract the most recently executed SQL string from AIMessage tool_calls."""
    for m in reversed(history):
        tool_calls = getattr(m, "tool_calls", None) or []
        for tc in tool_calls:
            if tc.get("name") == "execute_sql":
                args = tc.get("args", {})
                return args.get("query") or args.get("sql") or ""
    return ""


def _result_table_str(tool_content: Any, max_rows: int = 20) -> str:
    """Render the SQL result as a plain-text table for the verifier prompt."""
    text_content = _extract_tool_content(tool_content)
    if not text_content:
        return "(no result)"
    try:
        payload = json.loads(text_content)
    except (json.JSONDecodeError, TypeError):
        return text_content[:500]
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return f"(error) {payload.get('error_msg', '')}"
    rows = payload.get("rows") or []
    columns = payload.get("columns") or []
    if not rows:
        return "(query returned 0 rows)"
    header = " | ".join(columns)
    body = "\n".join(
        " | ".join(str(row.get(c, "")) for c in columns)
        for row in rows[:max_rows]
    )
    suffix = ""
    total = payload.get("row_count", len(rows))
    if total > max_rows:
        suffix = f"\n(showing {max_rows} of {total} rows)"
    return f"{header}\n{body}{suffix}"


def verify_node(state: AgentState) -> dict:
    """
    Ask the LLM whether the most recent SQL result correctly answers the user
    question. Up to _MAX_VERIFY_LOOPS rounds are allowed.

    Verdict CORRECT  → emit the final answer and set verified=True.
    Verdict RETRY    → inject a corrective HumanMessage so the next llm_node
                       turn rewrites and re-executes the SQL.
    """
    t0 = time.perf_counter()
    history = state.get("messages", [])
    verify_calls = state.get("verify_calls", 0)

    # Find the latest successful SQL result
    successful = [
        m for m in _tool_messages(history, "execute_sql")
        if _summarize_sql_result(state["user_query"], m.content) is not None
    ]

    # Guard: no SQL execution was even attempted (e.g. LLM answered directly)
    sql_attempts = _tool_messages(history, "execute_sql")
    if not sql_attempts:
        logger.info("verify_node: no SQL query was executed; skipping verification")
        return {
            "messages": [AIMessage(content="No query result was returned.")],
            "verify_calls": verify_calls + 1,
            "verified": True,
        }

    # If SQL was attempted, but none were successful, we have a failed SQL execution
    if not successful:
        last_attempt = sql_attempts[-1]
        try:
            text_content = _extract_tool_content(last_attempt.content)
            payload = json.loads(text_content) if text_content else {}
            error_msg = payload.get("error_msg") or "Unknown execution error"
        except (json.JSONDecodeError, TypeError, ValueError):
            error_msg = "Unknown execution error"
            
        sql = _extract_sql_from_history(history)
        
        if verify_calls >= _MAX_VERIFY_LOOPS:
            logger.warning(
                "verify_node: max verification loops (%d) reached with failed SQL; accepting error as-is",
                _MAX_VERIFY_LOOPS,
            )
            return {
                "messages": [AIMessage(content=f"SQL execution failed: {error_msg}")],
                "verify_calls": verify_calls + 1,
                "verified": True,
            }
        
        # Extract a targeted search term from the error so the forced RAG
        # re-retrieval is more specific than the original query.
        # Handles three Impala error classes:
        #   1. AnalysisException: Could not resolve table reference: 'bad.table'
        #   2. AnalysisException: Could not resolve column/field reference: 'alias.bad_col'
        #   3. ParseException: reserved keyword used as identifier (e.g. `element`)
        rag_query = state["user_query"]
        bad_identifier: str | None = None
        correction_hint: str = ""

        table_match = re.search(r"table reference: '([^']+)'", error_msg, re.IGNORECASE) or re.search(r"no such table: ([^\s\n]+)", error_msg, re.IGNORECASE)
        col_match   = re.search(r"column/field reference: '([^']+)'", error_msg, re.IGNORECASE) or re.search(r"no such column: ([^\s\n]+)", error_msg, re.IGNORECASE)
        parse_match = re.search(r"ParseException", error_msg, re.IGNORECASE) or re.search(r"syntax error", error_msg, re.IGNORECASE)

        if table_match:
            bad_table = table_match.group(1).split(".")[-1]  # strip db prefix
            bad_identifier = bad_table
            rag_query = (
                f"{state['user_query']} "
                f"(table '{bad_table}' does not exist — find its correct name in the schema)"
            )
            correction_hint = (
                f"The table '{bad_table}' does not exist in the database. "
                "Use ONLY table names returned by the schema retrieval above."
            )
        elif col_match:
            bad_col_full = col_match.group(1)           # e.g. "f.geography_id"
            bad_col = bad_col_full.split(".")[-1]        # e.g. "geography_id"
            bad_identifier = bad_col_full
            rag_query = (
                f"{state['user_query']} "
                f"(column '{bad_col}' does not exist — find its correct column name in the schema)"
            )
            correction_hint = (
                f"The column '{bad_col_full}' does not exist. "
                "Look at the schema retrieved above and use ONLY column names that appear there. "
                "Do NOT invent column names."
            )
        elif parse_match:
            # ParseException: usually a reserved keyword used as an alias
            # e.g. `element` — must be backtick-escaped in Impala
            kw_match = re.search(
                r"Encountered: Unknown last token.*?\n.*?\^.*?\nExpected:",
                error_msg,
                re.DOTALL,
            )
            bad_identifier = "(reserved keyword used as alias)"
            rag_query = f"{state['user_query']} (fix Impala SQL syntax error)"
            correction_hint = (
                "The SQL has a syntax error in Impala. "
                "Reserved keywords used as aliases (e.g. `element`, `date`, `value`) "
                "must be backtick-escaped. Also note: Impala requires `current_date()` "
                "(with parentheses), not bare `current_date`."
            )

        import uuid
        tool_call_id = f"call_{uuid.uuid4().hex}"
        forced_rag_msg = AIMessage(
            content=(
                f"Impala error: {error_msg}\n\n"
                f"{correction_hint}\n"
                "Retrieving the correct schema now so you can rewrite the SQL using only valid identifiers."
            ),
            tool_calls=[{
                "id": tool_call_id,
                "name": "retrive_schema_rag",
                "args": {
                    "query": rag_query,
                    "top_k": _RAG_TOP_K,
                }
            }]
        )
        logger.warning(
            "verify_node: SQL failed (bad_identifier=%s | error: %s). Forcing targeted RAG re-retrieval.",
            bad_identifier or "unknown",
            error_msg[:120],
        )
        return {
            "messages": [forced_rag_msg],
            "verify_calls": verify_calls + 1,
            "rag_calls": state.get("rag_calls", 0) + 1,
            "verified": False,
        }

    last_result_msg = successful[-1]
    result_table = _result_table_str(last_result_msg.content)
    summary = _summarize_sql_result(state["user_query"], last_result_msg.content)

    logger.info(
        "verify_node: query executed successfully — skipping LLM verification (%.2fs saved)",
        time.perf_counter() - t0,
    )
    return {
        "verify_calls": verify_calls + 1,
        "verified": True,
    }




# ─────────────────────────────────────────────────────────────────────────────
# Intent Classification & Entity Extraction (v1.4 Feature)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Intent Classification & Entity Extraction (v1.4 Feature)
# ─────────────────────────────────────────────────────────────────────────────

_GREETING_PATTERNS = re.compile(
    r"^(?:"
    r"hi+|hello+|hey+|greetings+|namaste+|good\s*(?:morning|afternoon|evening|day)|"
    r"howdy|hi\s*there|hello\s*there|hey\s*there|who\s*are\s*you|what\s*are\s*you|"
    r"how\s*are\s*you|welcome"
    r")(?:\s+(?:assistant|bot|there|friend|everyone|all))?[\s!.,?]*$",
    re.IGNORECASE,
)

_DOMAIN_KEYWORDS = {
    "student", "dropout", "scheme", "ration", "district", "aadhaar", "count",
    "list", "show", "find", "select", "where", "how many", "what is", "policy",
    "guideline", "mandal", "village", "school", "health", "land", "vehicle",
    "hospital", "income", "caste", "gender", "person", "household", "property",
    "epfo", "tax", "crop", "disbursement", "entitlement", "agriculture", "compliance",
    "avg", "sum", "total", "details", "info", "table", "sql", "data"
}


def _is_greeting_query(user_query: str) -> bool:
    if not user_query:
        return False
    clean_q = user_query.strip().lower()

    # 1. Exact or pattern match for common greetings
    if _GREETING_PATTERNS.match(clean_q):
        return True

    # 2. Short queries under 30 chars starting with a greeting word with no domain keywords
    words = set(re.findall(r"\b\w+\b", clean_q))
    greeting_words = {"hi", "hello", "hey", "greetings", "namaste", "howdy"}
    if len(clean_q) <= 30 and words.intersection(greeting_words):
        if not words.intersection(_DOMAIN_KEYWORDS):
            return True

    return False


INTENT_DEPARTMENT_MAP: dict[str, list[str]] = {
    "student_risk_list":             ["ap_citizen360"],
    "school_hotspot":                ["ap_citizen360"],
    "equity_risk_slice":             ["ap_citizen360"],
    "scheme_delivery_gap":           ["ap_citizen360"],
    "eligibility_blocker":           ["ap_citizen360"],
    "gsws_case_load":                ["ap_citizen360"],
    "household_poverty_risk":        ["ap_citizen360"],
    "citizen_socioeconomic_profile": ["ap_citizen360"],
    "teacher_attendance":            ["ap_citizen360"],
    "academic_performance":          ["ap_citizen360"],
    "greeting":                      [],
    "general_query":                 ["ap_citizen360"],
}


INTENT_DESCRIPTIONS = """
- student_risk_list: listing individual at-risk or dropout-risk students by absence, failure, or grade
- school_hotspot: identifying schools with high dropout risk, low attendance, or poor performance
- equity_risk_slice: analysis by social category (SC, ST, OBC), gender, or caste
- scheme_delivery_gap: welfare/benefit delivery failures — sanctioned but not disbursed
- eligibility_blocker: benefit eligibility flags not met (aadhaar, bank account, KYC, BPL)
- gsws_case_load: GSWS secretariat / gram sachivalayam caseload or mapping analysis
- household_poverty_risk: ration card / poverty household analysis linked to students
- citizen_socioeconomic_profile: citizen asset, land, property, utility, socioeconomic profiling
- teacher_attendance: teacher attendance records & teacher master profiling
- academic_performance: exam marks, scores, pass/fail, assessment analysis
- greeting: conversational greeting, salutation, or non-data introductory message (e.g. "hi", "hello", "good morning")
- general_query: anything that does not fit the above intents
"""

_intent_model = ChatOllama(
    model=_CHAT_MODEL,
    temperature=0,
    reasoning=False,
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    num_ctx=int(os.getenv("OLLAMA_INTENT_NUM_CTX", "2048")),
    num_predict=int(os.getenv("OLLAMA_INTENT_NUM_PREDICT", "256")),
)

_INTENT_SYSTEM_PROMPT = f"""You are an intent classifier for a school dropout monitoring system.

Given a user question, you must:
1. Classify it into EXACTLY ONE of these intents:
{INTENT_DESCRIPTIONS}

2. Classify the query_type:
   - "data_query": needs SQL (counts, lists, averages, specific data lookups)
   - "document_query": needs document context (policies, rules, procedures, guidelines, explanations of WHY something exists, eligibility criteria text)
   - "hybrid": needs BOTH data AND policy/document context
   - "greeting": conversational greeting or salutation (e.g. "hi", "hello", "good morning")

3. Extract these entities if mentioned (leave blank string "" if not present):
   - district_name: AP district (e.g. Guntur, Anantapur, Chittoor, Krishna, Kurnool, Srikakulam, Vizianagaram, Visakhapatnam, East Godavari, West Godavari, Prakasam, Nellore, Kadapa, YSR Kadapa)
   - academic_year: e.g. "2025", "2024-25", "2024"
   - current_grade: class/grade number e.g. "6", "8", "10"
   - social_category: e.g. "SC", "ST", "OBC", "General"

Respond with ONLY valid JSON — no explanation, no markdown, no extra text:
{{"intent": "...", "query_type": "...", "entities": {{"district_name": "...", "academic_year": "...", "current_grade": "...", "social_category": "..."}}}}"""


def _clean_llm_response(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_intent_response(raw: str) -> tuple[str, str, dict[str, str]]:
    try:
        cleaned = _clean_llm_response(raw)
        data = json.loads(cleaned)
        intent = data.get("intent", "general_query").strip()
        query_type = data.get("query_type", "data_query").strip()
        if intent not in INTENT_DEPARTMENT_MAP:
            logger.warning("intent_node: unknown intent '%s', falling back to general_query", intent)
            intent = "general_query"
        if query_type not in ("data_query", "document_query", "hybrid", "greeting"):
            query_type = "data_query"
        entities = {k: str(v) for k, v in data.get("entities", {}).items() if v}
        return intent, query_type, entities
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        logger.warning("intent_node: failed to parse LLM response (%s). Raw: %s", e, raw[:200])
        return "general_query", "data_query", {}


def intent_node(state: AgentState) -> dict:
    """
    LangGraph node: classify intent, query_type, and extract entities from user_query.

    Writes to state:
        intent          – 1 of 13 domain intent labels
        query_type      – "data_query" | "document_query" | "hybrid" | "greeting"
        department_scope – relevant database departments for RAG scoping
        entities        – extracted district, year, grade, social_category
    """
    t0 = time.perf_counter()
    user_query = state.get("user_query", "")

    # Guardrail check for pure greetings / salutations
    if _is_greeting_query(user_query):
        logger.info("intent_node: detected greeting query '%s'", user_query)
        return {
            "intent":           "greeting",
            "query_type":       "greeting",
            "department_scope": [],
            "entities":         {},
        }

    try:
        response = _intent_model.invoke([
            SystemMessage(content=_INTENT_SYSTEM_PROMPT),
            HumanMessage(content=f"User question: {user_query}"),
        ])
        raw_text = response.content or ""
        intent, query_type, entities = _parse_intent_response(raw_text)
    except Exception as e:
        logger.error("intent_node: LLM call failed (%s). Defaulting to general_query.", e)
        intent      = "general_query"
        query_type  = "data_query"
        entities    = {}

    department_scope = INTENT_DEPARTMENT_MAP.get(intent, ["school", "canonicalmodel"])

    logger.info(
        "intent_node: intent='%s' | query_type='%s' | scope=%s | entities=%s | %.2fs",
        intent, query_type, department_scope, entities, time.perf_counter() - t0,
    )

    return {
        "intent":           intent,
        "query_type":       query_type,
        "department_scope": department_scope,
        "entities":         entities,
    }


def initialize_node(state: AgentState) -> dict:
    """
    Graph entry point: force a retrieval RAG call on the user's raw query.

    If intent_node has already classified the query (state has 'intent' and
    'entities'), the RAG query is enriched with those signals so the vector
    search returns more relevant table chunks and fewer false positives.

    Enrichment strategy:
      - Prepend the classified intent so the embedding leans toward matching
        fewshot examples with the same intent label.
      - Append extracted entities (district, year, grade) as context hints.
      - Append department scope so embeddings for tables like citizen_school
        and school_student_attendance_fact rank higher than unrelated tables.
    """
    import uuid
    tool_call_id = f"call_{uuid.uuid4().hex}"

    raw_query    = state["user_query"]
    intent       = state.get("intent")
    entities     = state.get("entities") or {}
    dept_scope   = state.get("department_scope") or []

    # Use the RAW user query for vector search — not enriched.
    # Enrichment with [intent:...][district:...] metadata brackets corrupts
    # the embedding vector because the embedding model treats bracket tokens
    # as semantic content, pushing the vector away from fewshot embeddings
    # that were indexed with clean NL text only.
    rag_query = raw_query

    logger.info(
        "initialize_node: RAG query = %s  (intent=%s, entities=%s)",
        rag_query, intent, entities,
    )

    forced_tool_call_msg = AIMessage(
        content="",
        tool_calls=[{
            "id":   tool_call_id,
            "name": "retrive_schema_rag",
            "args": {
                "query": rag_query,
                "top_k": _RAG_TOP_K,
            }
        }]
    )

    return {
        "messages": [forced_tool_call_msg],
        "llm_calls": 0,
    }

# ─────────────────────────────────────────────────────────────────────────────
# Document Search and Synthesis Nodes
# ─────────────────────────────────────────────────────────────────────────────

def greeting_node(state: AgentState) -> dict:
    """
    Guardrail node for greeting queries.
    Returns a polite greeting response directing the user to ask database/data queries only.
    """
    response_text = (
        "Hello! 👋 Welcome to AP Citizen 360 AI Assistant.\n\n"
        "Please ask your question regarding the Citizen 360 database or policy documents in short."
    )
    return {
        "messages": [AIMessage(content=response_text)],
        "verified": True,
        "fast_sql": None,
    }


def route_node(state: AgentState) -> str:
    """Returns the next node name based on query_type."""
    qt = state.get("query_type", "data_query")
    if qt == "greeting":
        return "greeting_node"
    elif qt == "document_query":
        return "doc_search_node"
    elif qt == "hybrid":
        return "deterministic_search_node"  # Runs fast path check first
    return "deterministic_search_node"   # existing SQL path goes to fast path first

def deterministic_search_node(state: AgentState) -> dict:
    """Force-calls the search_exact_fewshot MCP tool to check for a 0.95+ cosine match."""
    import uuid
    tool_call_id = f"call_{uuid.uuid4().hex}"
    
    forced_tool_call_msg = AIMessage(
        content="",
        tool_calls=[{
            "id": tool_call_id,
            "name": "search_exact_fewshot",
            "args": {
                "query": state["user_query"],
                "threshold": 0.99
            }
        }]
    )
    
    return {
        "messages": [forced_tool_call_msg],
        "llm_calls": 0,
    }

def eval_fast_path_node(state: AgentState) -> dict:
    """
    Evaluates the result of search_exact_fewshot.
    If matched, it yields an AIMessage forcing execute_sql to bypass LLM generation.
    """
    import uuid
    history = state.get("messages", [])
    
    results = _tool_messages(history, "search_exact_fewshot")
    if not results:
        return {"fast_sql": None}
        
    try:
        content = _extract_tool_content(results[-1].content)
        payload = json.loads(content)
    except Exception:
        payload = {"matched": False}
        
    if payload.get("matched") and payload.get("sql"):
        sql = payload["sql"]
        tool_call_id = f"call_{uuid.uuid4().hex}"
        
        forced_execute_msg = AIMessage(
            content="I found an exact match for your query. Executing now.",
            tool_calls=[{
                "id": tool_call_id,
                "name": "execute_sql",
                "args": {
                    "query": sql
                }
            }]
        )
        return {
            "messages": [forced_execute_msg],
            "fast_sql": sql,
            "query_type": "fast_path"
        }
        
    return {"fast_sql": None}

def doc_search_node(state: AgentState) -> dict:
    """Force-calls the document search MCP tool."""
    import uuid
    tool_call_id = f"call_{uuid.uuid4().hex}"
    
    forced_tool_call_msg = AIMessage(
        content="",
        tool_calls=[{
            "id": tool_call_id,
            "name": "search_documents",
            "args": {
                "query": state["user_query"],
                "top_k": 5,
            }
        }]
    )
    
    return {
        "messages": [forced_tool_call_msg],
        "llm_calls": 0,
    }

def synthesize_node(state: AgentState) -> dict:
    """LLM call to synthesize document passages into a coherent answer."""
    t0 = time.perf_counter()
    history = state.get("messages", [])
    
    # Extract the passages returned by the search_documents tool
    doc_results = _tool_messages(history, "search_documents")
    if doc_results:
        doc_content = _extract_tool_content(doc_results[-1].content)
    else:
        doc_content = "No document passages were found."
    
    system_prompt = (
        "You are an assistant answering questions based on policy documents, circulars, and guidelines. "
        "Use ONLY the provided DOCUMENT PASSAGES to answer the user's question. "
        "If the answer is not in the passages, say so explicitly. "
        "When answering, cite the source document name and location. "
        "Summarize key points clearly and use bullet points for multi-part answers."
    )
    
    messages_for_llm = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User question: {state['user_query']}\n\n{doc_content}")
    ]
    
    model = _doc_synthesize_model  # Lightweight model with small context for doc synthesis
    response = model.invoke(messages_for_llm)
    
    logger.info("synthesize_node: completed in %.2fs", time.perf_counter() - t0)
    
    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }

def summarization_node(state: AgentState) -> dict:
    """LLM call to summarize the SQL result based on the user query."""
    t0 = time.perf_counter()
    history = state.get("messages", [])
    
    successful = _tool_messages(history, "execute_sql")
    if not successful:
        return {}
        
    last_result_msg = successful[-1]
    text_content = _extract_tool_content(last_result_msg.content)
    
    payload = {}
    if text_content:
        try:
            payload = json.loads(text_content)
        except Exception:
            pass
            
    if payload.get("status") != "success":
        return {}
        
    rows = payload.get("rows", [])
    if not rows:
        return {
            "messages": [AIMessage(content="The query ran successfully but returned no data.")],
        }
        
    result_table = _result_table_str(last_result_msg.content)
    
    system_prompt = (
        "You are an AI assistant. Summarize the following database query results in short based on the user's query.\n"
        "Do not explain the SQL query. Just provide a concise summary of the data table returned."
    )
    
    messages_for_llm = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User question: {state['user_query']}\n\nQuery result table:\n{result_table}")
    ]
    
    model = _summarize_model
    response = model.invoke(messages_for_llm)
    
    logger.info("summarization_node: completed in %.2fs", time.perf_counter() - t0)
    
    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }
