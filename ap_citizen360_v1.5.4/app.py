try:
    import sys
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
import asyncio
import json
import os
import sqlite3
import threading
import traceback
import uuid
import logging
from datetime import datetime
import time
from fastapi import Request
from auth_check import validate_issuer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True
)
logger = logging.getLogger("app")

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field

from database.suggestions import (
    get_fewshot_suggestions,
    get_cache_metadata,
    load_or_build_suggestions,
)
from database.valkey_queue import ValkeyQueueManager, JobStatus
from create_schema import create_database
from my_agent.agent import build_graph
from my_agent.utils.ollama_check import chat_model_name, check_ollama
from my_agent.utils.tools import cleanup_tools
from my_agent.utils.guardrails import ContentGuardrailManager

guardrail_manager: ContentGuardrailManager | None = None


def _get_guardrail_manager() -> ContentGuardrailManager:
    global guardrail_manager
    if guardrail_manager is None:
        guardrail_manager = ContentGuardrailManager()
    return guardrail_manager

# Speech-to-text imports
from speech_to_text.config import get_settings as get_speech_settings
from speech_to_text.transcriber import Transcriber
from speech_to_text.live import LiveTranscriptionSession, LiveSessionLimitError
from starlette.concurrency import run_in_threadpool
import base64
from fastapi import WebSocket, WebSocketDisconnect

speech_settings = get_speech_settings()
if speech_settings.enable_speech_to_text:
    speech_transcriber = Transcriber(speech_settings)
else:
    speech_transcriber = None


DB_PATH = os.path.join(os.path.dirname(__file__), "database", "schema.db")
HISTORY_DB_PATH = os.path.join(os.path.dirname(__file__), "database", "chat_history.db")
EXCEL_LOG_PATH = os.path.join(os.path.dirname(__file__), "database", "query_log.xlsx")
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
INDEX_HTML_PATH = TEMPLATES_DIR / "index.html"

# Thread lock for Excel file writes (openpyxl is not thread-safe)
_excel_lock = threading.Lock()

_EXCEL_HEADERS = [
    "Timestamp", "Username", "Session ID",
    "Question", "Generated SQL", "Status",
    "Answer / Response", "Error",
    "Gen Time (s)", "Exec Time (s)", "Total Time (s)"
]

ALLOWED_ISSUERS = {
    issuer.strip()
    for issuer in os.getenv("ALLOWED_ISSUERS", "sso-platform,YourIssuer").split(",")
    if issuer.strip()
}


def _init_excel_log() -> None:
    """Create the Excel log file with headers if it does not exist yet."""
    import openpyxl
    os.makedirs(os.path.dirname(EXCEL_LOG_PATH), exist_ok=True)
    if not os.path.exists(EXCEL_LOG_PATH):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Query Log"
        ws.append(_EXCEL_HEADERS)
        # Freeze the header row
        ws.freeze_panes = "A2"
        # Bold headers
        from openpyxl.styles import Font
        for cell in ws[1]:
            cell.font = Font(bold=True)
        wb.save(EXCEL_LOG_PATH)
        print(f"Excel query log initialized at {EXCEL_LOG_PATH}")


def _append_excel_log(
    username: str,
    session_id: str,
    question: str,
    sql: str,
    status: str,
    answer: str,
    error: str,
    gen_time: float = 0.0,
    exec_time: float = 0.0,
    total_time: float = 0.0,
) -> None:
    """Append one row to the Excel query log (thread-safe)."""
    import openpyxl
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        username,
        session_id,
        question,
        sql,
        status,
        answer[:2000] if answer else "",   # cap long answers
        error[:1000] if error else "",
        round(gen_time, 2),
        round(exec_time, 2),
        round(total_time, 2),
    ]
    with _excel_lock:
        try:
            wb = openpyxl.load_workbook(EXCEL_LOG_PATH)
            ws = wb.active
            # Ensure headers match if existing file has older schema
            if ws.max_row >= 1 and ws.cell(row=1, column=ws.max_column).value != "Total Time (s)":
                for col_idx, header in enumerate(_EXCEL_HEADERS, start=1):
                    ws.cell(row=1, column=col_idx, value=header)
            ws.append(row)
            wb.save(EXCEL_LOG_PATH)
        except Exception as exc:
            print(f"[excel_log] Failed to write row: {exc}")


# Mapping of active request IDs to their running asyncio Tasks
active_tasks: dict[str, asyncio.Task] = {}


class AskRequest(BaseModel):
    action: str | None = Field(
        default=None,
        description="Action to perform: 'ask', 'queue_status', 'job_status', 'suggestions', 'suggestions_meta', 'cancel', 'history', 'history_session', 'delete_session', 'clear_history', 'chart', 'speech_to_text'",
    )
    question: str | None = Field(default=None, description="Natural-language question.")
    request_id: str | None = Field(
        None,
        description="Unique ID generated by the UI to track and cancel this request.",
    )
    session_id: str | None = Field(default=None, description="Optional chat session ID for conversation memory.")
    thread_id: str | None = Field(default=None, description="Optional chat thread ID (alias for session_id) for conversation memory.")
    chart_type: str | None = Field(default=None, description="Type of chart (e.g., 'bar', 'line', 'pie', 'scatter') for 'chart' action.")
    data: list[dict[str, Any]] | None = Field(default=None, description="Data to be plotted for 'chart' action.")
    audio_base64: str | None = Field(default=None, description="Base64 encoded audio for 'speech_to_text' action.")
    username: str = Field(default="user", description="Required username to scope the chat history.")
    limit: int | None = Field(default=-1, description="Optional limit for suggestion count (-1 returns all).")


class AskResponse(BaseModel):
    sql: str
    result: list[dict[str, Any]]
    username: str = Field(..., description="The username associated with this chat.")
    timings: dict[str, float] | None = None
    summary: str | None = None

class SessionSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class MessageDetail(BaseModel):
    id: str
    role: str
    content: str
    sql: str | None = None
    result: list[dict[str, Any]] | None = None
    created_at: str


class SessionDetail(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[MessageDetail]


def init_database() -> None:
    """Initialize curated sample database if missing or still on the old schema."""
    should_create = not os.path.exists(DB_PATH)
    if not should_create:
        try:
            conn = sqlite3.connect(DB_PATH)
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            conn.close()
            should_create = "citizen_student" not in tables or "students" in tables
        except sqlite3.Error:
            should_create = True

    if should_create:
        create_database(DB_PATH, replace=True)
        print(f"Curated database initialized at {DB_PATH}")


def init_history_database() -> None:
    """Initialize SQLite database for chat history and sessions."""
    os.makedirs(os.path.dirname(HISTORY_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(HISTORY_DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                username TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sql TEXT,
                result TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN username TEXT;")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        print(f"Chat history database initialized at {HISTORY_DB_PATH}")
    except sqlite3.Error as e:
        print(f"Error initializing chat history database: {e}")
    finally:
        conn.close()


def get_session_messages(session_id: str) -> list[Any]:
    """Load messages from db and convert them to LangGraph message list."""
    conn = sqlite3.connect(HISTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content, sql FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 10",
            (session_id,)
        )
        rows = cursor.fetchall()
        rows.reverse()
        messages = []
        for row in rows:
            if row["role"] == "user":
                messages.append(HumanMessage(content=row["content"]))
            elif row["role"] == "assistant":
                # Include SQL in the assistant message so the LLM can reference
                # it for follow-up questions (e.g. "now filter by female students")
                content = row["content"] or ""
                if row["sql"]:
                    content = f"{content}\n\n[SQL used: `{row['sql']}`]"
                messages.append(AIMessage(content=content))
        return messages
    except sqlite3.Error as e:
        print(f"Database error while reading session messages: {e}")
        return []
    finally:
        conn.close()



def save_chat_turn(session_id: str, question: str, response_text: str, sql: str | None, result: list[dict[str, Any]] | None, username: str | None = None) -> str:
    """Save user and assistant messages, update session updated_at, return session_id."""
    conn = sqlite3.connect(HISTORY_DB_PATH)
    now = datetime.now().isoformat()
    try:
        cursor = conn.cursor()
        
        # Check if session exists
        cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        session_exists = cursor.fetchone() is not None
        
        if not session_exists:
            # Generate a title from the first question (first 60 chars)
            title = question[:60] + ("..." if len(question) > 60 else "")
            cursor.execute(
                "INSERT INTO sessions (id, title, username, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, title, username, now, now)
            )
        else:
            # Update updated_at
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id)
            )
            if username:
                cursor.execute(
                    "UPDATE sessions SET username = ? WHERE id = ? AND username IS NULL",
                    (username, session_id)
                )
            
        # Save user message
        user_msg_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_msg_id, session_id, "user", question, now)
        )
        
        # Save assistant message
        assistant_msg_id = str(uuid.uuid4())
        result_json = json.dumps(result) if result is not None else None
        cursor.execute(
            "INSERT INTO messages (id, session_id, role, content, sql, result, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (assistant_msg_id, session_id, "assistant", response_text, sql, result_json, now)
        )
        
        conn.commit()
        return session_id
    except sqlite3.Error as e:
        print(f"Database error while saving chat turn: {e}")
        return session_id
    finally:
        conn.close()


def _http_error_from_exc(exc: Exception) -> HTTPException:
    msg = str(exc)
    model = chat_model_name()
    if "not found" in msg.lower() and "model" in msg.lower():
        return HTTPException(
            status_code=503,
            detail=(
                f"Ollama model '{model}' is not installed. "
                f"Run: ollama pull {model} - then restart uvicorn. ({msg})"
            ),
        )
    return HTTPException(status_code=500, detail=msg)


def _extract_tool_content(message: Any) -> str | None:
    """Extract plain-text content from a ToolMessage.

    MCP adapters may deliver content as a plain string OR as a list of
    content blocks (e.g. [{"type": "text", "text": "..."}]).  Handle both.
    """
    raw = getattr(message, "content", None)
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                return item
            if isinstance(item, dict) and item.get("type") == "text":
                return item.get("text")
    return str(raw)


def _extract_sql_and_result(messages: list[Any], username: str) -> AskResponse:
    from langchain_core.messages import ToolMessage as LCToolMessage

    sql = None
    result: list[dict[str, Any]] | None = None

    for message in messages:
        # ── extract SQL from any AIMessage tool call ──────────────────────────
        for tool_call in getattr(message, "tool_calls", None) or []:
            args = tool_call.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if tool_call.get("name") == "execute_sql" and args.get("query"):
                sql = args["query"]

        # ── extract rows from any execute_sql ToolMessage ─────────────────────
        is_tool_msg = isinstance(message, LCToolMessage) or (
            message.__class__.__name__ == "ToolMessage"
        )
        if not is_tool_msg:
            continue

        tool_name = getattr(message, "name", None)
        if tool_name != "execute_sql":
            continue

        raw_content = _extract_tool_content(message)
        if not raw_content:
            continue

        try:
            payload = json.loads(raw_content)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

        if payload.get("status") == "success":
            result = payload.get("rows") or []

    # If SQL was not found, default to empty string
    if sql is None:
        sql = ""

    # If result was not found (meaning failure or no execution), build a fallback explanation result
    if result is None:
        error_msg = None
        # Try to find an error status in execute_sql ToolMessages
        for message in reversed(messages):
            is_tool_msg = isinstance(message, LCToolMessage) or (
                message.__class__.__name__ == "ToolMessage"
            )
            if is_tool_msg and getattr(message, "name", None) == "execute_sql":
                raw_content = _extract_tool_content(message)
                if raw_content:
                    try:
                        payload = json.loads(raw_content)
                        if payload.get("status") == "error":
                            error_msg = payload.get("error_msg") or payload.get("error_type")
                            if error_msg:
                                break
                    except Exception:
                        pass

        # If no tool error, look for any final explanation AIMessage
        if not error_msg:
            for message in reversed(messages):
                msg_class = message.__class__.__name__
                if msg_class == "AIMessage" or getattr(message, "content", None):
                    # Make sure it's not a tool call message
                    if not getattr(message, "tool_calls", None):
                        content = getattr(message, "content", None)
                        if content and isinstance(content, str) and content.strip():
                            error_msg = content.strip()
                            break

        if not error_msg:
            error_msg = "The agent did not return an executed SQL query."

        result = [{"error": error_msg, "status": "failed"}]

    return AskResponse(sql=sql, result=result, username=username)



queue_manager = ValkeyQueueManager()


async def _execute_graph_query(job: dict) -> dict:
    """Execute a single query job pulled by a consumer worker."""
    question = job.get("question", "")
    username = job.get("username", "user")
    session_id = job.get("session_id", "")

    # Content guardrail validation (defense-in-depth in worker)
    gm = _get_guardrail_manager()
    if gm:
        is_valid, violation_msg, violation_details = gm.validate(question)
        if not is_valid:
            logger.warning(
                "🛡️ [GUARDRAIL BLOCKED in worker] User: %s | Reason: %s | Query: %s",
                username, violation_msg, question
            )
            return {
                "sql": "",
                "result": [{
                    "error": f"Content Policy Violation: {violation_msg}",
                    "status": "blocked",
                    "details": violation_details
                }],
                "username": username,
                "summary": f"I cannot process this query. {violation_msg}",
                "gen_time": 0.0,
                "exec_time": 0.0,
                "total_time": 0.0,
            }

    ollama_info = check_ollama()
    if not ollama_info.get("model_available"):
        return {
            "sql": "",
            "result": [{
                "error": f"Ollama model '{chat_model_name()}' is not available. Run: ollama pull {chat_model_name()} — then restart uvicorn.",
                "status": "failed"
            }],
            "username": username,
            "summary": "Ollama model not available.",
            "gen_time": 0.0,
            "exec_time": 0.0,
            "total_time": 0.0,
        }

    graph = await _get_graph()
    history_messages = get_session_messages(session_id)

    t_start = time.perf_counter()
    state = await graph.ainvoke(
        {
            "user_query": question,
            "messages": history_messages + [HumanMessage(content=question)],
            "retrieved_context": [],
            "llm_calls": 0,
            "rag_calls": 0,
            "verify_calls": 0,
            "verified": False,
            "intent": None,
            "department_scope": None,
            "entities": None,
        }
    )
    total_time = time.perf_counter() - t_start
    gen_time = state.get("gen_time", 0.0)
    exec_time = state.get("exec_time", 0.0)

    response_obj = _extract_sql_and_result(state.get("messages", []), username)
    response_obj.timings = {
        "total_gen_time": round(gen_time, 2),
        "total_exec_time": round(exec_time, 2),
        "total_time": round(total_time, 2)
    }

    # Extract verbal assistant summary
    response_text = ""
    for msg in reversed(state.get("messages", [])):
        if msg.__class__.__name__ == "AIMessage" or getattr(msg, "type", None) == "ai":
            if not getattr(msg, "tool_calls", None) and getattr(msg, "content", ""):
                response_text = msg.content
                break
    if not response_text:
        if response_obj.result and isinstance(response_obj.result, list) and len(response_obj.result) > 0 and "error" in response_obj.result[0]:
            response_text = response_obj.result[0]["error"]
        else:
            response_text = "Here is the query result."

    response_obj.summary = response_text

    is_greeting = state.get("intent") == "greeting"
    if not is_greeting:
        save_chat_turn(
            session_id=session_id,
            question=question,
            response_text=response_text,
            sql=response_obj.sql,
            result=response_obj.result,
            username=username
        )
        is_error = (
            response_obj.result
            and len(response_obj.result) > 0
            and response_obj.result[0].get("status") in ("failed", "cancelled")
        )
        excel_status = response_obj.result[0].get("status", "success") if is_error else "success"
        excel_error = response_obj.result[0].get("error", "") if is_error else ""
        _append_excel_log(
            username=username,
            session_id=session_id,
            question=question or "",
            sql=response_obj.sql or "",
            status=excel_status,
            answer=response_text,
            error=excel_error,
            gen_time=gen_time,
            exec_time=exec_time,
            total_time=total_time,
        )

    res_dict = response_obj.model_dump()
    res_dict["gen_time"] = gen_time
    res_dict["exec_time"] = exec_time
    res_dict["total_time"] = total_time
    return res_dict

queue_manager.set_executor(_execute_graph_query)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    init_history_database()
    _init_excel_log()
    global guardrail_manager
    try:
        guardrail_manager = ContentGuardrailManager()
        logger.info("Content guardrails initialized in lifespan.")
    except Exception as e:
        logger.warning("Failed to initialize ContentGuardrailManager: %s", e)
        guardrail_manager = None
    ollama_status = check_ollama()
    app.state.ollama_status = ollama_status
    app.state.graph = None
    app.state.graph_lock = asyncio.Lock()
    if not ollama_status.get("model_available"):
        print("WARNING: Ollama chat model not available:", ollama_status)
    else:
        print("Ollama ready:", ollama_status.get("model"))
        try:
            app.state.graph = await build_graph()
            print("LangGraph agent built successfully during startup.")
        except Exception as e:
            app.state.graph = None
            print(f"Failed to build LangGraph agent during startup: {e}")
            traceback.print_exc()

    if speech_settings.enable_speech_to_text and speech_transcriber:
        print("Speech-to-text enabled. Loading faster-whisper model...")
        speech_settings.upload_dir.mkdir(parents=True, exist_ok=True)

    # Start Valkey parallel consumer workers
    queue_manager.start_workers()

    yield

    # Shutdown workers and cleanup
    await queue_manager.stop_workers()
    if app.state.graph is not None:
        await cleanup_tools()
    if speech_settings.enable_speech_to_text and speech_transcriber:
        speech_transcriber.unload_model()


async def _get_graph():
    if app.state.graph is None:
        async with app.state.graph_lock:
            if app.state.graph is None:
                app.state.graph = await build_graph()
    return app.state.graph


app = FastAPI(
    title="Student Dropout Intent API",
    version="1.5.4",
    description="API backend for natural-language SQL with Intent Classification (v1.5.4).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    info = check_ollama()
    q_metrics = await queue_manager.get_metrics()
    return {
        "status": "ok" if info.get("model_available") else "degraded",
        "queue": {
            "backend": q_metrics.get("backend"),
            "concurrency": q_metrics.get("concurrency_limit"),
            "active_workers": q_metrics.get("active_workers"),
            "queued_jobs": q_metrics.get("queued_jobs"),
            "total_completed": q_metrics.get("total_completed"),
        },
        **info,
    }


@app.post("/ask")
@validate_issuer
async def ask(payload: AskRequest, request: Request):
    action = payload.action or "ask"
    username = payload.username

    # 0. Action: Suggestions Cache Metadata / Version check
    if action in ("suggestions_meta", "suggestions_version"):
        return get_cache_metadata()

    # 0b. Action: Suggestions / Few-shots (raw list, NO backend ranking)
    elif action in ("suggestions", "fewshots", "get_suggestions"):
        limit = payload.limit if payload.limit is not None else -1
        items = get_fewshot_suggestions(limit=limit)
        meta = get_cache_metadata()
        return {
            "status": "success",
            "count": len(items),
            "updated_at": meta["updated_at"],
            "suggestions": items,
        }

    # 0c. Action: Queue Status / Metrics
    elif action in ("queue_status", "queue_metrics", "queue"):
        return await queue_manager.get_metrics()

    # 0d. Action: Job Status (check specific job)
    elif action in ("job_status", "check_job"):
        req_id = payload.request_id
        if not req_id:
            raise HTTPException(status_code=400, detail="request_id is required for job_status action")
        job = queue_manager.get_job(req_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {req_id} not found")
        return job

    # 1. Action: Cancel
    elif action == "cancel":
        req_id = payload.request_id
        if not req_id:
            raise HTTPException(status_code=400, detail="request_id is required for cancel action")
        cancelled = await queue_manager.cancel_job(req_id)
        task = active_tasks.get(req_id)
        if task and not task.done():
            task.cancel()
        if cancelled or task:
            return {"status": "success", "message": f"Request {req_id} cancellation signal sent."}
        return {
            "status": "not_found",
            "message": f"Request {req_id} is not active or has already completed.",
        }

    # 2. Action: History (list all sessions — returns titles and dates only)
    elif action == "history":
        conn = sqlite3.connect(HISTORY_DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE username = ? ORDER BY updated_at DESC",
                (username,)
            )
            session_rows = cursor.fetchall()
            sessions = [
                SessionSummary(
                    id=row["id"],
                    title=row["title"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in session_rows
            ]
            return sessions
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch chat history: {e}")
        finally:
            conn.close()

    # 2b. Action: History Session (fetch full message context for a given session_id)
    elif action == "history_session":
        session_id = payload.session_id or payload.thread_id
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required for history_session action")
        conn = sqlite3.connect(HISTORY_DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, username, created_at, updated_at FROM sessions WHERE id = ? AND username = ?",
                (session_id, username)
            )
            s_row = cursor.fetchone()
            if not s_row:
                raise HTTPException(status_code=404, detail="Session not found")

            cursor.execute(
                "SELECT id, role, content, sql, result, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,)
            )
            msg_rows = cursor.fetchall()
            messages = []
            for r in msg_rows:
                res_val = None
                if r["result"]:
                    try:
                        res_val = json.loads(r["result"])
                    except Exception:
                        res_val = []
                messages.append(
                    MessageDetail(
                        id=r["id"],
                        role=r["role"],
                        content=r["content"],
                        sql=r["sql"],
                        result=res_val,
                        created_at=r["created_at"],
                    )
                )
            return SessionDetail(
                id=s_row["id"],
                title=s_row["title"],
                created_at=s_row["created_at"],
                updated_at=s_row["updated_at"],
                messages=messages,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch session context: {e}")
        finally:
            conn.close()

    # 3. Action: Delete Session
    elif action == "delete_session":
        session_id = payload.session_id or payload.thread_id
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required for delete_session action")
        conn = sqlite3.connect(HISTORY_DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if not row or row[0] != username:
                raise HTTPException(status_code=404, detail="Chat session not found")

            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return {"status": "success", "message": "Session deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete session: {e}")
        finally:
            conn.close()

    # 4. Action: Clear History
    elif action == "clear_history":
        conn = sqlite3.connect(HISTORY_DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE username = ?)", (username,))
            cursor.execute("DELETE FROM sessions WHERE username = ?", (username,))
            conn.commit()
            return {"status": "success", "message": "All sessions deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear sessions: {e}")
        finally:
            conn.close()

    # 4b. Action: Chart (generate Vega-Lite SVG)
    elif action == "chart":
        if not payload.data or not payload.chart_type:
            raise HTTPException(status_code=400, detail="Both 'data' and 'chart_type' are required for chart action.")
        
        try:
            # Import dynamically to avoid loading vl-convert if unused
            from my_agent.utils.chart_generator import generate_svg_chart
            svg = generate_svg_chart(payload.data, payload.chart_type)
            return {"status": "success", "svg": svg}
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to generate chart: {e}")

    # 4c. Action: Speech to Text (Offline file base64)
    elif action == "speech_to_text":
        if not speech_settings.enable_speech_to_text or not speech_transcriber:
            raise HTTPException(status_code=503, detail="Speech-to-text is not enabled.")
        if not payload.audio_base64:
            raise HTTPException(status_code=400, detail="audio_base64 is required for speech_to_text action.")
        try:
            audio_bytes = base64.b64decode(payload.audio_base64)
            upload_path = speech_settings.upload_dir / f"{uuid.uuid4().hex}.wav"
            with upload_path.open("wb") as f:
                f.write(audio_bytes)
            
            result = await run_in_threadpool(speech_transcriber.transcribe, upload_path)
            
            try:
                if upload_path.exists():
                    upload_path.unlink()
            except OSError:
                pass

            return AskResponse(sql="", result=[{"text": result.text}], username=username)
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to transcribe audio: {e}")

    # 5. Action: Ask (NL2SQL Query via Valkey FIFO Queue)
    elif action == "ask":
        if not payload.question:
            raise HTTPException(status_code=400, detail="question is required for ask action")

        req_id = payload.request_id or f"req_{uuid.uuid4().hex[:12]}"
        session_id = payload.session_id or payload.thread_id or str(uuid.uuid4())

        logger.info("=" * 60)
        logger.info("📥 [NEW QUERY RECEIVED]")
        logger.info("   User:       %s", username)
        logger.info("   Session:    %s", session_id)
        logger.info("   Request ID: %s", req_id)
        logger.info("   Question:   %s", payload.question)
        logger.info("=" * 60)

        # Content guardrail validation (reject harmful, nonsensical, or profane input early)
        gm = _get_guardrail_manager()
        if gm:
            is_valid, violation_msg, violation_details = gm.validate(payload.question)
            if not is_valid:
                logger.warning(
                    "🛡️ [GUARDRAIL BLOCKED] User: %s | Reason: %s | Query: %s",
                    username, violation_msg, payload.question
                )
                async def _blocked_stream():
                    yield json.dumps({
                        "sql": "",
                        "result": [{
                            "error": f"Content Policy Violation: {violation_msg}",
                            "status": "blocked",
                            "details": violation_details
                        }],
                        "summary": f"I cannot process this query. {violation_msg}",
                        "username": username,
                        "timings": {"total_time": 0.0}
                    }).encode()
                return StreamingResponse(
                    _blocked_stream(),
                    media_type="application/json",
                    headers={
                        "X-Accel-Buffering": "no",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    }
                )

        # Enqueue non-blockingly in strict FIFO order
        job_id = await queue_manager.enqueue_job(
            question=payload.question,
            username=username,
            session_id=session_id,
            request_id=req_id,
        )

        async def _stream():
            try:
                # Keepalive loop: stream keepalive space every 10 seconds while
                # waiting in queue or during LLM processing to prevent proxy timeouts.
                KEEPALIVE_INTERVAL = 10.0
                POLL_INTERVAL = 0.1
                elapsed = 0.0

                while True:
                    job = queue_manager.get_job(job_id)
                    if job and job.get("status") in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                        break

                    await asyncio.sleep(POLL_INTERVAL)
                    elapsed += POLL_INTERVAL
                    if elapsed >= KEEPALIVE_INTERVAL:
                        yield b" "  # keepalive — resets IIS / proxy 120s timeout
                        elapsed = 0.0

                job = queue_manager.get_job(job_id) or {}
                status = job.get("status")

                if status == JobStatus.CANCELLED:
                    yield json.dumps({
                        "sql": "",
                        "result": [{"error": "Request cancelled.", "status": "cancelled"}],
                        "username": username
                    }).encode()
                elif job.get("result"):
                    yield json.dumps(job["result"]).encode()
                elif job.get("error"):
                    yield json.dumps({
                        "sql": "",
                        "result": [{"error": job["error"], "status": "failed"}],
                        "username": username
                    }).encode()
                else:
                    yield json.dumps({
                        "sql": "",
                        "result": [{"error": "The agent did not return an executed SQL query.", "status": "failed"}],
                        "username": username
                    }).encode()

            except asyncio.CancelledError:
                await queue_manager.cancel_job(job_id)
                yield json.dumps({
                    "sql": "",
                    "result": [{"error": "Request cancelled.", "status": "cancelled"}],
                    "username": username
                }).encode()
            except Exception as exc:
                logger.error("Error in streaming response for job %s: %s", job_id, exc, exc_info=True)
                yield json.dumps({
                    "sql": "",
                    "result": [{"error": str(exc), "status": "failed"}],
                    "username": username
                }).encode()

        return StreamingResponse(
            _stream(),
            media_type="application/json",
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")


@app.websocket("/ws/transcribe/live")
async def live_transcription(websocket: WebSocket) -> None:
    await websocket.accept()

    if not speech_settings.enable_speech_to_text or not speech_transcriber:
        await websocket.send_json({"type": "error", "detail": "Speech-to-text is not enabled"})
        await websocket.close(code=1008)
        return

    try:
        start_message = await websocket.receive_text()
        start_payload = json.loads(start_message)
    except (WebSocketDisconnect, json.JSONDecodeError):
        await websocket.send_json({"type": "error", "detail": "First message must be JSON"})
        await websocket.close(code=1003)
        return

    if start_payload.get("type") != "start":
        await websocket.send_json({"type": "error", "detail": "First message type must be start"})
        await websocket.close(code=1003)
        return

    try:
        sample_rate = int(start_payload.get("sample_rate") or 0)
    except (TypeError, ValueError):
        await websocket.send_json({"type": "error", "detail": f"sample_rate must be {speech_settings.live_sample_rate}"})
        await websocket.close(code=1003)
        return
        
    if sample_rate != speech_settings.live_sample_rate:
        await websocket.send_json({"type": "error", "detail": f"sample_rate must be {speech_settings.live_sample_rate}"})
        await websocket.close(code=1003)
        return

    session = LiveTranscriptionSession(
        transcriber=speech_transcriber,
        sample_rate=speech_settings.live_sample_rate,
        chunk_seconds=speech_settings.live_chunk_seconds,
        max_session_seconds=speech_settings.live_max_session_seconds,
    )
    await websocket.send_json({"type": "ready"})

    try:
        while True:
            message = await websocket.receive()

            if message.get("bytes") is not None:
                try:
                    events = await run_in_threadpool(session.receive_audio, message["bytes"])
                except LiveSessionLimitError as exc:
                    await websocket.send_json({"type": "error", "detail": str(exc)})
                    await websocket.close(code=1009)
                    return

                for event in events:
                    await websocket.send_json(event)
                continue

            text = message.get("text")
            if text is None:
                continue

            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Text messages must be JSON"})
                continue

            if payload.get("type") == "stop":
                final_event = await run_in_threadpool(session.flush)
                await websocket.send_json(final_event)
                await websocket.close(code=1000)
                return

            await websocket.send_json({"type": "error", "detail": "Unsupported message type"})
    except WebSocketDisconnect:
        pass


@app.get("/suggestions/meta")
@app.get("/suggestions/version")
async def get_suggestions_meta_endpoint():
    """Returns timestamp and count metadata of few-shot suggestions cache for UI caching validation."""
    return get_cache_metadata()


@app.get("/suggestions")
@app.get("/fewshots")
async def get_suggestions_endpoint(
    limit: int = Query(default=-1, description="Maximum suggestions to return (-1 for all)"),
):
    """Retrieve raw few-shot questions and vector embeddings (all ranking handled client-side in UI)."""
    items = get_fewshot_suggestions(limit=limit)
    
    # Append dynamic queried caches from Valkey
    try:
        from database.valkey_cache import ValkeyCacheManager
        valkey_queries = ValkeyCacheManager().get_all_cached_queries()
        if valkey_queries:
            # We insert valkey queries at the beginning so they show up prominently
            items = valkey_queries + items
    except Exception as e:
        logger.error(f"Failed to fetch dynamic queries from Valkey for suggestions: {e}")

    meta = get_cache_metadata()
    return {
        "status": "success",
        "count": len(items),
        "updated_at": meta["updated_at"],
        "suggestions": items,
    }


@app.post("/suggestions")
async def post_suggestions_endpoint(payload: AskRequest):
    """Alternate POST endpoint for few-shot suggestions and vector embeddings."""
    if not payload.action:
        payload.action = "suggestions"
    return await ask(payload)


@app.get("/", response_class=HTMLResponse)
async def get_ui():
    if not INDEX_HTML_PATH.exists():
        raise HTTPException(status_code=404, detail="index.html template not found")
    return HTMLResponse(content=INDEX_HTML_PATH.read_text(encoding="utf-8"))

