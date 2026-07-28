import operator
from typing import List, Dict, Any
from typing_extensions import Annotated, NotRequired, TypedDict
from langchain_core.messages import AnyMessage


class AgentState(TypedDict):
    # Original user query
    user_query: str

    # Context chunks returned by RAG MCP server
    retrieved_context: List[Dict[str, Any]]

    # Full conversation / tool-call message history
    messages: Annotated[List[AnyMessage], operator.add]

    # Tracks how many times the LLM has been invoked
    llm_calls: int

    # Tracks how many RAG (retrive_schema_rag) calls have been made
    rag_calls: int

    # Set when a template SQL fast-path is used (skip extra LLM turns)
    fast_sql: NotRequired[str | None]

    # Tracks how many verification rounds have run (max 5)
    verify_calls: int

    # True once the LLM confirms the SQL result is correct
    verified: bool

    # ── Intent node additions ─────────────────────────────────────────────────

    # Classified intent label (e.g. "student_risk_list", "school_hotspot")
    intent: NotRequired[str | None]

    # Department scope derived from YAML 'department' field
    # e.g. ["school", "canonicalmodel"] — drives RAG query enrichment
    department_scope: NotRequired[List[str] | None]

    # Extracted entities: district_name, academic_year, current_grade, social_category
    entities: NotRequired[Dict[str, str] | None]

    # ── Document routing additions ────────────────────────────────────────────

    # Query routing classification set by intent_node:
    #   "data_query"     → SQL path only (existing pipeline)
    #   "document_query" → Document RAG + LLM synthesis path
    #   "hybrid"         → Both paths (SQL + document context)
    query_type: NotRequired[str | None]

    # Formatted document passages returned by search_documents MCP tool.
    # Stored here so synthesize_node can read them from state directly.
    doc_context: NotRequired[str | None]

    # List of source filenames cited in the document answer (for UI display)
    doc_sources: NotRequired[List[str] | None]
