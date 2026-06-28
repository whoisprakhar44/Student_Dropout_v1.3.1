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

_HIVE_ENABLED = os.getenv("HIVE_MCP_ENABLED", "false").strip().lower() in ("true", "1", "yes")
_RAG_TOP_K = int(os.getenv("RAG_TOP_K", "15"))

if _HIVE_ENABLED:
    SYSTEM_PROMPT = """You are a SQL data assistant with a live Hive / Apache Spark SQL database for the curated_datamodels data model.

Available tools:
- retrive_schema_rag: retrieve curated table DDL, key joins, columns, and rules when you need schema context.
- execute_sql: execute read-only Hive SQL SELECT queries against the database.

STRICT RULES — follow every rule without exception:
1. For ANY question about counts, totals, lists, averages, rates, trends, or data values — you MUST call execute_sql.
2. ALWAYS call retrive_schema_rag FIRST before writing any SQL. Use ONLY the exact table names and column names returned by retrive_schema_rag — never invent or guess names. If a table you need is not in the retrieved results, call retrive_schema_rag again with a more specific query describing what that table contains.
3. If execute_sql fails with a table-not-found or column-not-found error, do NOT retry the same SQL. Call retrive_schema_rag again with a targeted query to find the correct table/column names, then rewrite the SQL.
4. NEVER describe DDL or schema to the user — always run execute_sql and report the actual data.
5. NEVER answer without calling execute_sql for data questions.
6. After execute_sql returns rows, summarize the result in plain language.
7. The database is Hive/Impala - use Hive/Spark-compatible SQL only. Always prefix table names with the database (e.g. `curated_datamodels.table_name`).
8. NEVER guess, invent, or assume any table names, column names, or join relations. If you lack the DDL context or column definitions for a table, you MUST call retrive_schema_rag to retrieve it. Do not attempt to guess or invent columns/tables under any circumstances.
"""
else:
    SYSTEM_PROMPT = """You are a SQL data assistant with a live SQLite sample database for the curated_datamodels school data model.

Available tools:
- retrive_schema_rag: retrieve curated table DDL, key joins, columns, and rules when you need schema context.
- execute_sql: execute read-only SQLite SELECT queries against the sample database.

STRICT RULES — follow every rule without exception:
1. For ANY question about counts, totals, lists, averages, rates, trends, or data values — you MUST call execute_sql.
2. ALWAYS call retrive_schema_rag FIRST before writing any SQL. Use ONLY the exact table names and column names returned by retrive_schema_rag. NEVER guess, invent, or assume any table names, column names, or join relations. If you lack the DDL context or column definitions for a table, you MUST call retrive_schema_rag to retrieve it. Do not attempt to guess or invent columns/tables under any circumstances.
3. NEVER describe DDL or schema to the user — always run execute_sql and report the actual data.
4. NEVER answer without calling execute_sql for data questions.
5. After execute_sql returns rows, summarize the result in plain language.
6. The database is SQLite - use SQLite-compatible SQL only. All tables are in the main schema with no prefix (e.g. write `citizen_student` instead of `curated_datamodels.citizen_student`).
"""


def _get_model():
    global _model_with_tools
    if _model_with_tools is None:
        if not tool_registry.execution_tools:
            raise RuntimeError(
                "Tools not loaded. Make sure init_tools() was awaited before compiling the graph."
            )
        _model_with_tools = _base_model.bind_tools(tool_registry.execution_tools)
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
    max_llm_calls = int(os.getenv("MAX_LLM_CALLS", "15"))
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
                "verified": True,
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
            "verified": True,
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
        messages_for_llm.append(SystemMessage(
            content=(
                "The schema context above contains two sections:\n"
                "1. REFERENCE SQL EXAMPLES \u2014 use these as a structural pattern for your query.\n"
                "2. SCHEMA DDLs \u2014 these are the authoritative table and column names. "
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

    logger.info("llm_node: completed in %.2fs", time.perf_counter() - t0)
    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + llm_steps,
    }


def build_tool_node() -> ToolNode:
    """Returns a ToolNode bound to SQL and RAG MCP tools."""
    if not tool_registry.execution_tools:
        raise RuntimeError("Tools not loaded before building tool node.")
    return ToolNode(tool_registry.execution_tools)


# ---------------------------------------------------------------------------
# Verification node
# ---------------------------------------------------------------------------
_MAX_VERIFY_LOOPS = int(os.getenv("MAX_VERIFY_LOOPS", "10"))

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
        
        # Extract a targeted search term from the error (e.g. the bad table name)
        # so the forced RAG re-retrieval is more specific than the original query.
        rag_query = state["user_query"]
        table_match = re.search(r"table reference: '([^']+)'", error_msg, re.IGNORECASE)
        if table_match:
            bad_table = table_match.group(1).split(".")[-1]  # strip db prefix
            rag_query = f"{state['user_query']} (looking for table similar to: {bad_table})"

        import uuid
        tool_call_id = f"call_{uuid.uuid4().hex}"
        forced_rag_msg = AIMessage(
            content=(
                f"SQL failed: {error_msg}. "
                "Calling schema retrieval to find the correct table and column names before retrying."
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
            "verify_node: SQL failed execution (error: %s). Forcing RAG re-retrieval before correction.",
            error_msg,
        )
        return {
            "messages": [forced_rag_msg],
            "verify_calls": verify_calls + 1,
            "verified": False,
        }

    last_result_msg = successful[-1]
    sql = _extract_sql_from_history(history)
    result_table = _result_table_str(last_result_msg.content)

    # Hard cap: if we have exhausted all verify loops, accept the current result
    if verify_calls >= _MAX_VERIFY_LOOPS:
        logger.warning(
            "verify_node: max verification loops (%d) reached; accepting result as-is",
            _MAX_VERIFY_LOOPS,
        )
        summary = _summarize_sql_result(state["user_query"], last_result_msg.content)
        return {
            "messages": [AIMessage(content=summary or result_table)],
            "verify_calls": verify_calls + 1,
            "verified": True,
        }

    # Build and call the verifier
    verifier_prompt = _VERIFY_PROMPT.format(
        user_query=state["user_query"],
        sql=sql or "(SQL not captured)",
        result_table=result_table,
    )
    verdict_response = _base_model.invoke([
        SystemMessage(content=(
            "You are a strict SQL result verifier. "
            "Your only job is to decide whether a SQL query result correctly and completely answers the user's question. "
            "Reply with EXACTLY 'CORRECT: <reason>' or 'RETRY: <reason>'. No other output."
        )),
        HumanMessage(content=verifier_prompt),
    ])
    verdict_text = (verdict_response.content or "").strip()
    logger.info(
        "verify_node [round %d]: raw verdict=%s  (%.2fs)",
        verify_calls + 1,
        verdict_text[:80],
        time.perf_counter() - t0,
    )

    # Clean up thinking/reasoning tags
    clean_verdict = re.sub(r"<think>.*?(?:</think>|$)", "", verdict_text, flags=re.DOTALL).strip()
    if not clean_verdict:
        clean_verdict = verdict_text

    if clean_verdict.upper().startswith("CORRECT"):
        # Result is verified — produce the final pretty summary
        summary = _summarize_sql_result(state["user_query"], last_result_msg.content)
        final_answer = summary or result_table
        logger.info("verify_node: result verified as CORRECT in round %d", verify_calls + 1)
        return {
            "messages": [AIMessage(content=final_answer)],
            "verify_calls": verify_calls + 1,
            "verified": True,
        }

    # RETRY path — extract the reason and inject a corrective instruction
    retry_reason = clean_verdict.split(":", 1)[-1].strip() if ":" in clean_verdict else clean_verdict
    correction_msg = HumanMessage(
        content=(
            f'The previous SQL result did NOT correctly answer: "{state["user_query"]}"\n'
            f"Reason: {retry_reason}\n\n"
            f"The SQL that was run:\n{sql}\n\n"
            "Please call execute_sql again with a corrected query that fixes the issue described above."
        )
    )
    logger.info("verify_node: RETRY round %d — injecting correction", verify_calls + 1)
    return {
        "messages": [correction_msg],
        "verify_calls": verify_calls + 1,
        "verified": False,
    }




# ─────────────────────────────────────────────────────────────────────────────
# Intent Classification & Entity Extraction (v1.4 Feature)
# ─────────────────────────────────────────────────────────────────────────────

INTENT_DEPARTMENT_MAP: dict[str, list[str]] = {
    "student_risk_list":             ["school", "canonicalmodel"],
    "school_hotspot":                ["school", "canonicalmodel"],
    "equity_risk_slice":             ["school", "canonicalmodel"],
    "scheme_delivery_gap":           ["school", "canonicalmodel"],
    "eligibility_blocker":           ["school", "canonicalmodel"],
    "gsws_case_load":                ["school", "canonicalmodel"],
    "nutrition_service_gap":         ["school", "canonicalmodel"],
    "facility_root_cause":           ["school", "canonicalmodel"],
    "household_poverty_risk":        ["canonicalmodel"],
    "citizen_socioeconomic_profile": ["canonicalmodel"],
    "teacher_attendance":            ["school", "canonicalmodel"],
    "academic_performance":          ["school", "canonicalmodel"],
    "general_query":                 ["school", "canonicalmodel"],
}

INTENT_DESCRIPTIONS = """
- student_risk_list: listing individual at-risk or dropout-risk students by absence, failure, or grade
- school_hotspot: identifying schools with high dropout risk, low attendance, or poor performance
- equity_risk_slice: analysis by social category (SC, ST, OBC), gender, or caste
- scheme_delivery_gap: welfare/benefit delivery failures — sanctioned but not disbursed
- eligibility_blocker: benefit eligibility flags not met (aadhaar, bank account, KYC, BPL)
- gsws_case_load: GSWS secretariat / gram sachivalayam caseload or mapping analysis
- nutrition_service_gap: mid-day meal / nutrition serving analysis
- facility_root_cause: school infrastructure or facility issues (toilet, water, electricity, ICT)
- household_poverty_risk: ration card / poverty household analysis linked to students
- citizen_socioeconomic_profile: citizen asset, land, property, utility, socioeconomic profiling
- teacher_attendance: teacher attendance records & teacher master profiling
- academic_performance: exam marks, scores, pass/fail, assessment analysis
- general_query: anything that does not fit the above intents
"""

_intent_model = ChatOllama(
    model=_CHAT_MODEL,
    temperature=0,
    reasoning=False,
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "4096")),
    num_predict=256,
)

_INTENT_SYSTEM_PROMPT = f"""You are an intent classifier for a school dropout monitoring system.

Given a user question, you must:
1. Classify it into EXACTLY ONE of these intents:
{INTENT_DESCRIPTIONS}

2. Extract these entities if mentioned (leave blank string "" if not present):
   - district_name: AP district (e.g. Guntur, Anantapur, Chittoor, Krishna, Kurnool, Srikakulam, Vizianagaram, Visakhapatnam, East Godavari, West Godavari, Prakasam, Nellore, Kadapa, YSR Kadapa)
   - academic_year: e.g. "2025", "2024-25", "2024"
   - current_grade: class/grade number e.g. "6", "8", "10"
   - social_category: e.g. "SC", "ST", "OBC", "General"

Respond with ONLY valid JSON — no explanation, no markdown, no extra text:
{{"intent": "...", "entities": {{"district_name": "...", "academic_year": "...", "current_grade": "...", "social_category": "..."}}}}"""


def _clean_llm_response(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_intent_response(raw: str) -> tuple[str, dict[str, str]]:
    try:
        cleaned = _clean_llm_response(raw)
        data = json.loads(cleaned)
        intent = data.get("intent", "general_query").strip()
        if intent not in INTENT_DEPARTMENT_MAP:
            logger.warning("intent_node: unknown intent '%s', falling back to general_query", intent)
            intent = "general_query"
        entities = {k: str(v) for k, v in data.get("entities", {}).items() if v}
        return intent, entities
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        logger.warning("intent_node: failed to parse LLM response (%s). Raw: %s", e, raw[:200])
        return "general_query", {}


def intent_node(state: AgentState) -> dict:
    """
    LangGraph node: classify intent and extract entities from user_query.
    Writes to state: intent, department_scope, entities.
    """
    t0 = time.perf_counter()
    user_query = state.get("user_query", "")

    try:
        response = _intent_model.invoke([
            SystemMessage(content=_INTENT_SYSTEM_PROMPT),
            HumanMessage(content=f"User question: {user_query}"),
        ])
        raw_text = response.content or ""
        intent, entities = _parse_intent_response(raw_text)
    except Exception as e:
        logger.error("intent_node: LLM call failed (%s). Defaulting to general_query.", e)
        intent = "general_query"
        entities = {}

    department_scope = INTENT_DEPARTMENT_MAP.get(intent, ["school", "canonicalmodel"])

    logger.info(
        "intent_node: intent='%s' | scope=%s | entities=%s | %.2fs",
        intent, department_scope, entities, time.perf_counter() - t0,
    )

    return {
        "intent": intent,
        "department_scope": department_scope,
        "entities": entities,
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

    # Build enriched RAG query
    if intent and intent != "general_query":
        enriched_parts = [f"[intent: {intent}]", raw_query]

        # Add entity context so embedding is grounded in specific values
        entity_hints = []
        if entities.get("district_name"):
            entity_hints.append(f"district: {entities['district_name']}")
        if entities.get("academic_year"):
            entity_hints.append(f"year: {entities['academic_year']}")
        if entities.get("current_grade"):
            entity_hints.append(f"grade: {entities['current_grade']}")
        if entities.get("social_category"):
            entity_hints.append(f"category: {entities['social_category']}")
        if entity_hints:
            enriched_parts.append(f"[{', '.join(entity_hints)}]")

        # Add department scope so RAG biases toward the right table set
        if dept_scope:
            enriched_parts.append(f"[departments: {', '.join(dept_scope)}]")

        rag_query = " ".join(enriched_parts)
    else:
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

