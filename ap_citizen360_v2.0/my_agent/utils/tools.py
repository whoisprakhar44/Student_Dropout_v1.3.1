"""
tools.py
--------
Initialises both MCP clients and exposes:
  - rag_tool       : the single retrieve tool from the RAG server
  - execution_tools: SQL execution tools plus LLM-selectable RAG tools
  - all_tools      : same list, kept for compatibility
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from langchain_mcp_adapters.client import MultiServerMCPClient, load_mcp_tools

BASE_DIR = str(Path(__file__).resolve().parents[2])
load_dotenv(os.path.join(BASE_DIR, ".env"))

RAG_SERVER_PATH  = os.path.join(BASE_DIR, "MCP", "mcp_rag.py")
RAG_CONFIG_PATH  = os.path.join(BASE_DIR, "MCP", "mcp_rag.yaml")

HIVE_ENABLED = os.getenv("HIVE_MCP_ENABLED", "false").strip().lower() in ("true", "1", "yes")
if HIVE_ENABLED:
    TOOL_SERVER_PATH = os.path.join(BASE_DIR, "MCP", "mcp_hive_execution.py")
else:
    TOOL_SERVER_PATH = os.path.join(BASE_DIR, "MCP", "mcp_sql_execution.py")

SQLITE_DB_PATH   = os.path.join(BASE_DIR, "database", "schema.db")

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
RAG_HOST = os.getenv("RAG_HOST", "localhost")
RAG_PORT = int(os.getenv("RAG_PORT", "8000"))
TOOL_HOST = os.getenv("TOOL_HOST", "localhost")
TOOL_PORT = int(os.getenv("TOOL_PORT", "8001"))

if MCP_TRANSPORT == "sse":
    RAG_SERVER_CONFIG = {
        "rag": {
            "transport": "sse",
            "url": f"http://{RAG_HOST}:{RAG_PORT}/sse",
        }
    }
    TOOL_SERVER_CONFIG = {
        "tools": {
            "transport": "sse",
            "url": f"http://{TOOL_HOST}:{TOOL_PORT}/sse",
        }
    }
else:
    RAG_SERVER_CONFIG = {
        "rag": {
            "command": sys.executable,
            "args": [RAG_SERVER_PATH],
            "transport": "stdio",
            "env": {
                **os.environ,
                "RETRIEVAL_CONFIG": RAG_CONFIG_PATH,
            },
        }
    }
    
    TOOL_SERVER_CONFIG = {
        "tools": {
            "command": sys.executable,
            "args": [TOOL_SERVER_PATH],
            "transport": "stdio",
            "env": {
                **os.environ,
                "SQLITE_DATABASE_PATH": SQLITE_DB_PATH,
                "RETRIEVAL_CONFIG": RAG_CONFIG_PATH,
            },
        }
    }

# ── module-level tool lists (populated by init_tools) ─────────────────────────
rag_tool: object = None
doc_tool: object = None          # search_documents MCP tool
execution_tools: list = []       # all tools visible to the LLM during SQL path
doc_search_tools: list = []      # only search_documents (used during doc path)
all_tools: list = []

# ── keep session context managers alive for the app lifetime ──────────────────
_rag_session_ctx  = None
_tool_session_ctx = None

async def init_tools() -> None:
    global rag_tool, doc_tool, execution_tools, doc_search_tools, all_tools
    global _rag_session_ctx, _tool_session_ctx

    _rag_client  = MultiServerMCPClient(RAG_SERVER_CONFIG)
    _tool_client = MultiServerMCPClient(TOOL_SERVER_CONFIG)

    # Open sessions and hold them open — subprocesses stay alive
    _rag_session_ctx  = _rag_client.session("rag")
    _tool_session_ctx = _tool_client.session("tools")

    rag_session  = await _rag_session_ctx.__aenter__()
    tool_session = await _tool_session_ctx.__aenter__()

    rag_tools_list  = await load_mcp_tools(rag_session)
    sql_tools_list  = await load_mcp_tools(tool_session)

    if not rag_tools_list:
        raise RuntimeError("RAG MCP server returned no tools.")
    if not sql_tools_list:
        raise RuntimeError("Execution MCP server returned no tools.")

    col_val_tool = None
    global check_fewshot_tool
    check_fewshot_tool = None
    
    for t in rag_tools_list:
        if t.name == "retrive_schema_rag":
            rag_tool = t
        elif t.name == "search_documents":
            doc_tool = t
        elif t.name == "get_column_values":
            col_val_tool = t
        elif t.name == "check_fewshot_similarity":
            check_fewshot_tool = t

    if not rag_tool or not doc_tool:
        raise RuntimeError("RAG server did not return both tools.")

    # SQL path tools: schema RAG + column values + SQL execution
    execution_tools.clear()
    tools_to_add = [rag_tool]
    if col_val_tool:
        tools_to_add.append(col_val_tool)
    execution_tools.extend(tools_to_add + sql_tools_list)

    # Document path tools: only search_documents
    doc_search_tools.clear()
    doc_search_tools.extend([doc_tool])

    # all_tools: everything the LLM can ever call
    all_tools.clear()
    all_tools.extend(execution_tools)

    print("RAG tool loaded :", rag_tool.name)
    if doc_tool:
        print("Doc tool loaded :", doc_tool.name, "(Disabled from LLM)")
    if check_fewshot_tool:
        print("Fewshot tool loaded:", check_fewshot_tool.name)
    print("LLM tools loaded:", [t.name for t in all_tools])


async def cleanup_tools() -> None:
    """Call once on app shutdown to terminate subprocesses cleanly."""
    global _rag_session_ctx, _tool_session_ctx
    for ctx in (_rag_session_ctx, _tool_session_ctx):
        if not ctx:
            continue
        try:
            await ctx.__aexit__(None, None, None)
        except BaseException:
            pass
    _rag_session_ctx = None
    _tool_session_ctx = None
