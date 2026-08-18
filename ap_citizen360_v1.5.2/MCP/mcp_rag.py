try:
    import sys
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

import re

import sys
import logging
import json

# =========================
# LOGGING — must be FIRST before any other imports
# =========================
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True  # overrides any handlers already set by faiss/other libs
)

logging.getLogger("faiss").setLevel(logging.ERROR)
logging.getLogger("faiss.loader").setLevel(logging.ERROR)
logging.getLogger("milvus_lite").setLevel(logging.ERROR)
logging.getLogger("milvus_lite.server_manager").setLevel(logging.ERROR)

logger = logging.getLogger("schema-retrieval")

# =========================
# OTHER IMPORTS — after logging is set up
# =========================
import os
import yaml
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()


# =========================
# CONFIG
# =========================
def load_config() -> dict:
    path = os.environ.get("RETRIEVAL_CONFIG", "mcp_rag.yaml")
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(path, "r") as f:
        return yaml.safe_load(f)


# =========================
# EMBEDDINGS
# =========================
PARTITION_DOCS = "document_store"

class Embedder:
    def __init__(self, cfg):
        self.provider = cfg["embedding"]["provider"]
        self.model = cfg["embedding"]["model"]

        if self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI()

        elif self.provider == "sentence_transformers":
            from sentence_transformers import SentenceTransformer
            self.client = SentenceTransformer(self.model)

        elif self.provider == "ollama":
            import requests
            self.requests = requests
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
            self.url = cfg["embedding"].get("ollama_url", f"{base_url}/api/embeddings")

    def embed(self, text: str):
        if self.provider == "openai":
            res = self.client.embeddings.create(model=self.model, input=[text])
            return res.data[0].embedding

        if self.provider == "sentence_transformers":
            return self.client.encode([text])[0].tolist()

        if self.provider == "ollama":
            res = self.requests.post(
                self.url,
                json={"model": self.model, "prompt": text}
            )
            return res.json()["embedding"]


# =========================
# VECTOR DB
# =========================
class VectorDB:
    def __init__(self, cfg):
        self.provider = cfg["vector_db"]["provider"]

        if self.provider == "chromadb":
            import chromadb
            self.client = chromadb.PersistentClient(
                path=cfg["vector_db"]["chromadb"]["path"]
            )
            self.col = self.client.get_collection(
                cfg["vector_db"]["chromadb"]["collection"]
            )

        elif self.provider == "milvus":
            from pymilvus import MilvusClient
            _uri = cfg["vector_db"]["milvus"]["uri"]
            if not _uri.startswith(("http://", "https://")) and not os.path.isabs(_uri):
                # Resolve relative to project root (ap_citizen360_v1.5.2) which is parent of MCP
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                _uri = os.path.join(project_root, _uri)
            self.client = MilvusClient(uri=_uri)
            self.collection = cfg["vector_db"]["milvus"]["collection"]
            self.client.load_collection(self.collection)
        else:
            raise ValueError(f"Unsupported vector_db provider: {self.provider}")

    def search(self, embedding, top_k: int):
        if self.provider == "chromadb":
            res = self.col.query(
                query_embeddings=[embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            return [
                {
                    "database_name": m["database_name"],
                    "table_name": m["table_name"],
                    "raw_ddl": m["raw_ddl"],
                    "embedding_text": d,
                    "score": 1 - dist
                }
                for d, m, dist in zip(
                    res["documents"][0],
                    res["metadatas"][0],
                    res["distances"][0]
                )
            ]
        elif self.provider=="milvus":
            # Split top_k as a COMBINED budget so total chunks never exceed top_k.
            # Fix 3: increased fewshot budget from 1/3 to 1/2 — fewshot SQL
            # patterns are the strongest signal for correct query generation.
            n_fewshot = max(2, top_k // 2)
            n_schema  = max(1, top_k - n_fewshot)

            # ── Search schema_store (actual DDL) ─────────────────────────────
            schema_res = self.client.search(
                collection_name=self.collection,
                data=[embedding],
                limit=n_schema,
                output_fields=["database_name", "table_name", "raw_ddl", "embedding_text"],
                search_params={"metric_type": "COSINE"},
                partition_names=["schema_store"],
            )
            schema_hits = [
                {
                    "database_name": hit["entity"]["database_name"],
                    "table_name":    hit["entity"]["table_name"],
                    "raw_ddl":       hit["entity"]["raw_ddl"],
                    "embedding_text":hit["entity"]["embedding_text"],
                    "score":         hit["distance"],
                    "chunk_type":    "schema_ddl",
                }
                for hit in schema_res[0]
            ]

            # ── Search few_shot_store (SQL examples) ─────────────────────────
            try:
                fewshot_res = self.client.search(
                    collection_name=self.collection,
                    data=[embedding],
                    limit=n_fewshot,
                    output_fields=["database_name", "table_name", "raw_ddl", "embedding_text"],
                    search_params={"metric_type": "COSINE"},
                    partition_names=["few_shot_store"],
                )
                fewshot_hits = [
                    {
                        "database_name": hit["entity"]["database_name"],
                        "table_name":    hit["entity"]["table_name"],
                        "raw_ddl":       hit["entity"]["raw_ddl"],
                        "embedding_text":hit["entity"]["embedding_text"],
                        "score":         hit["distance"],
                        "chunk_type":    "few_shot_example",
                    }
                    for hit in fewshot_res[0]
                ]
            except Exception as e:
                import traceback
                logger.error(f"Error searching few_shot_store: {e}")
                logger.error(traceback.format_exc())
                fewshot_hits = []

            # ── Fix 5: Keyword fallback — ensure schema chunks exist for
            #    tables mentioned in fewshot SQL results ───────────────────
            schema_hits = _ensure_fewshot_tables_in_schema(
                self, fewshot_hits, schema_hits
            )

            # Few-shot examples first (highest semantic signal),
            # then schema DDLs so the LLM sees exact column names after examples.
            return fewshot_hits + schema_hits

        else:
            raise ValueError(f"Unsupported vector_db provider: {self.provider}")

# =========================
# POST PROCESSING
# =========================

# Fix 4: Configurable schema threshold (lowered from 0.35 to 0.20).
# The old 0.35 threshold silently dropped schema chunks when the embedding
# model produced low scores, leaving the LLM with zero DDL context.
_SCHEMA_MIN_SCORE = float(os.getenv("SCHEMA_MIN_SCORE", "0.20"))

# Fact tables excluded from RAG results.
# These are Data Transfer API infrastructure tables and P4/population aggregates
# that have no analytical value for the Student Dropout NL2SQL use-case.
# The Milvus index and metadata structure are unchanged — exclusion happens
# purely at query-time, after vector search returns results.
# Fact tables excluded from RAG results (empty by default for AP Citizen 360)
EXCLUDED_FACT_TABLES: set[str] = set(
    x.strip() for x in os.getenv("EXCLUDED_FACT_TABLES", "").split(",") if x.strip()
)



def dedupe(rows: List[Dict]):
    seen = set()
    out = []
    for r in rows:
        if r.get("chunk_type") == "few_shot_example":
            key = ("few_shot", r.get("embedding_text", ""))
        else:
            key = (r["database_name"], r["table_name"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def threshold(rows: List[Dict], min_score: float = _SCHEMA_MIN_SCORE):
    return [r for r in rows if r["score"] >= min_score or r.get("chunk_type") == "few_shot_example"]


def exclude_facts(rows: List[Dict]) -> List[Dict]:
    """Drop schema_ddl chunks whose table_name is in EXCLUDED_FACT_TABLES.
    Few-shot examples are never filtered — they don't expose harmful DDL
    and removing them would degrade query-pattern matching."""
    out = []
    for r in rows:
        if r.get("chunk_type") == "few_shot_example":
            out.append(r)
        elif r.get("table_name") in EXCLUDED_FACT_TABLES:
            logger.debug("exclude_facts: dropped %s", r.get("table_name"))
        else:
            out.append(r)
    return out


def _ensure_fewshot_tables_in_schema(
    vdb: 'VectorDB',
    fewshot_hits: List[Dict],
    schema_hits: List[Dict],
) -> List[Dict]:
    """Fix 5: Keyword fallback — if fewshot SQL mentions tables that are not
    in the schema results, pull them from Milvus by scalar filter so the LLM
    has both the SQL pattern AND the DDL for those tables."""
    if not fewshot_hits or vdb.provider != "milvus":
        return schema_hits

    # Extract table names from fewshot SQL (raw_ddl contains the gold SQL)
    mentioned_tables: set[str] = set()
    for fs in fewshot_hits:
        sql = fs.get("raw_ddl", "")
        for match in re.findall(
            r'(?:ap_citizen360)\.(\w+)', sql
        ):
            mentioned_tables.add(match)

    # Check which ones are already in schema results
    existing_tables = {h["table_name"] for h in schema_hits}
    missing_tables = mentioned_tables - existing_tables

    if not missing_tables:
        return schema_hits

    # Query Milvus for the missing tables by scalar filter
    try:
        filter_expr = "table_name in [{}]".format(
            ", ".join(f'"{t}"' for t in missing_tables)
        )
        extra = vdb.client.query(
            collection_name=vdb.collection,
            filter=filter_expr,
            output_fields=["database_name", "table_name", "raw_ddl", "embedding_text"],
            partition_names=["schema_store"],
            limit=len(missing_tables),
        )
        for row in extra:
            schema_hits.append({
                "database_name": row["database_name"],
                "table_name":    row["table_name"],
                "raw_ddl":       row["raw_ddl"],
                "embedding_text":row["embedding_text"],
                "score":         0.50,  # synthetic score for keyword-matched chunks
                "chunk_type":    "schema_ddl",
            })
        if extra:
            logger.info(
                "_ensure_fewshot_tables_in_schema: backfilled %d table(s): %s",
                len(extra),
                [r["table_name"] for r in extra],
            )
    except Exception as e:
        logger.warning("_ensure_fewshot_tables_in_schema: fallback failed: %s", e)

    return schema_hits


# =========================
# INIT
# =========================
try:
    cfg = load_config()
    embedder = Embedder(cfg)
    vector_db = VectorDB(cfg)
    logger.info("Startup successful")
except Exception:
    logger.exception("Startup failed")  # ← logs to stderr, never stdout
    sys.exit(1)                          # ← clean exit, no stdout pollution

mcp = FastMCP("schema-retrieval")


# =========================
# MCP TOOL
# =========================
@mcp.tool()
def retrive_schema_rag(query: str, top_k: int = 15):
    logger.info(f"Query: {query}")
    emb = embedder.embed(query)
    results = vector_db.search(emb, top_k)
    results = dedupe(results)
    results = threshold(results)
    results = exclude_facts(results)
    
    logger.info(f"RAG retrieved {len(results)} chunks for query '{query}':")
    for idx, hit in enumerate(results):
        logger.info(f"  [{idx+1}] Table: {hit['database_name']}.{hit['table_name']} | Similarity Score: {hit['score']:.4f}")
    
    hive_enabled = os.getenv("HIVE_MCP_ENABLED", "false").strip().lower() in ("true", "1", "yes")
    if not hive_enabled:
        import re
        for hit in results:
            # 1. Clean raw_ddl
            ddl = hit.get("raw_ddl", "")
            if ddl:
                ddl = ddl.replace("ap_citizen360.", "")
                ddl = ddl.replace("CREATE EXTERNAL TABLE", "CREATE TABLE")
                for term in ["USING ICEBERG", "PARTITIONED BY", "LOCATION", "TBLPROPERTIES"]:
                    idx = ddl.find(term)
                    if idx != -1:
                        prefix = ddl[:idx].rstrip()
                        if prefix.endswith(")"):
                            ddl = prefix + ";"
                        else:
                            last_paren = prefix.rfind(")")
                            if last_paren != -1:
                                ddl = prefix[:last_paren+1] + ";"
                        break
                ddl = re.sub(r"\bSTRING\b", "TEXT", ddl, flags=re.IGNORECASE)
                ddl = re.sub(r"\bBIGINT\b", "INTEGER", ddl, flags=re.IGNORECASE)
                ddl = re.sub(r"\bDECIMAL\(\d+,\s*\d+\)", "REAL", ddl, flags=re.IGNORECASE)
                ddl = re.sub(r"\bTIMESTAMP\b", "TEXT", ddl, flags=re.IGNORECASE)
                hit["raw_ddl"] = ddl

            # 2. Clean embedding_text
            emb_text = hit.get("embedding_text", "")
            if emb_text:
                emb_text = emb_text.replace("Database: ap_citizen360", "Database: SQLite")
                emb_text = emb_text.replace("ap_citizen360.", "")
                emb_text = re.sub(r"\bSTRING\b", "TEXT", emb_text)
                emb_text = re.sub(r"\bBIGINT\b", "INTEGER", emb_text)
                emb_text = re.sub(r"\bDECIMAL\(\d+,\s*\d+\)", "REAL", emb_text)
                emb_text = re.sub(r"\bTIMESTAMP\b", "TEXT", emb_text)
                if "DDL:" in emb_text:
                    parts = emb_text.split("DDL:")
                    main_part = parts[0]
                    ddl_part = parts[1]
                    ddl_part = ddl_part.replace("CREATE EXTERNAL TABLE", "CREATE TABLE")
                    for term in ["USING ICEBERG", "PARTITIONED BY", "LOCATION", "TBLPROPERTIES"]:
                        idx = ddl_part.find(term)
                        if idx != -1:
                            prefix = ddl_part[:idx].rstrip()
                            if prefix.endswith(")"):
                                ddl_part = prefix + ";"
                            else:
                                last_paren = ddl_part.rfind(")")
                                if last_paren != -1:
                                    ddl_part = ddl_part[:last_paren+1] + ";"
                            break
                    emb_text = main_part + "DDL:\n" + ddl_part.strip()
                hit["embedding_text"] = emb_text

            # 3. Clean database_name
            hit["database_name"] = "SQLite"

    logger.info(f"Returned {len(results)} chunks")

    # Format output as a structured string so the LLM clearly distinguishes
    # few-shot SQL examples from schema DDL definitions.
    # - few-shots  → raw_ddl   (contains the actual SQL example to follow)
    # - schema DDL → embedding_text (compact curated summary; raw_ddl is ~3x
    #   larger due to STORED AS / LOCATION / TBLPROPERTIES Hive boilerplate
    #   that wastes context tokens without helping the LLM write SQL)
    sections = []
    fewshot_items = [r for r in results if r.get("chunk_type") == "few_shot_example"]
    schema_items  = [r for r in results if r.get("chunk_type") != "few_shot_example"]

    if fewshot_items:
        sections.append("=== REFERENCE SQL EXAMPLES (use these as a pattern, but verify column names against the DDLs below) ===")
        for r in fewshot_items:
            payload = r.get("raw_ddl", "") or r.get("embedding_text", "")
            sections.append(f"[Example | score={r['score']:.3f}]\n{payload}")

    if schema_items:
        sections.append("=== SCHEMA DDLs (authoritative table and column names — use ONLY these names in your SQL) ===")
        for r in schema_items:
            # embedding_text is a compact summary (~100-150 tokens vs ~400 for raw_ddl)
            content = r.get("embedding_text") or r.get("raw_ddl", "")
            sections.append(f"[DDL: {r['database_name']}.{r['table_name']} | score={r['score']:.3f}]\n{content}")

    return "\n\n".join(sections) if sections else str(results)


# =========================
# RUN
# =========================
@mcp.tool()
def get_column_values(table: str, column: str) -> str:
    """
    Look up known distinct values for a specific table column (e.g. district names, 
    academic years, school management types). 
    Use this INSTEAD of running SELECT DISTINCT queries.
    """
    import yaml
    from pathlib import Path
    
    # Locate the YAML file for this table
    yaml_dir = Path(__file__).parent.parent / "schema" / "curated_datamodels" / "tables"
    # The table might be passed as ap_citizen360.dim_student or just dim_student
    table_name = table.split(".")[-1]
    yaml_files = list(yaml_dir.rglob(f"{table_name}.yaml"))
    
    if not yaml_files:
        return f"Could not find schema definition for table '{table}'."
        
    try:
        with open(yaml_files[0], "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)
            
        if not doc or "columns" not in doc:
            return f"No columns found in schema for table '{table}'."
            
        for col in doc["columns"]:
            if col.get("name", "").lower() == column.lower():
                val_desc = col.get("value_description", "")
                distinct = col.get("distinct", [])
                samples = col.get("sample_values", [])
                
                res = []
                if val_desc:
                    res.append(f"Known values: {val_desc}")
                if distinct:
                    res.append(f"Distinct values: {', '.join(str(d) for d in distinct)}")
                if samples:
                    res.append(f"Samples: {', '.join(str(s) for s in samples)}")
                    
                if res:
                    return f"Values for {table}.{column}:\n" + "\n".join(res)
                else:
                    return f"No predefined distinct values found for {table}.{column}. You may need to run SELECT DISTINCT."
                    
        return f"Column '{column}' not found in table '{table}'."
    except Exception as e:
        logger.error(f"Error reading schema for {table}: {e}")
        return f"Error reading values for {table}.{column}."


@mcp.tool()
def search_documents(query: str, top_k: int = 5) -> str:
    """
    Search unstructured documents (PDFs, DOCX, TXT files) for passages that
    are relevant to the query.

    Use this tool when the user asks about:
    - Policies, rules, regulations, guidelines, circulars
    - Eligibility criteria, procedures, definitions
    - Anything that would be found in a document rather than a database table

    Returns ranked text passages with source document name and location
    (page number or section) for citations.
    """
    logger.info("search_documents query: %s (top_k=%d)", query, top_k)
    
    try:
        embedding = embedder.embed(query)
        results = vector_db.client.search(
            collection_name=vector_db.collection,
            data=[embedding],
            limit=top_k,
            output_fields=["database_name", "table_name", "raw_ddl", "embedding_text"],
            search_params={"metric_type": "COSINE"},
            partition_names=[PARTITION_DOCS],
        )
    except Exception as e:
        logger.warning("search_documents failed (partition may be empty): %s", e)
        return "No relevant document passages found for this query."

    if not results or not results[0]:
        return "No relevant document passages found for this query."

    hits = []
    for hit in results[0]:
        score = float(hit["distance"]) # COSINE metric returns similarity in Milvus
        if score < 0.35: # MIN_SCORE
            continue
        hits.append({
            "score":         score,
            "source_file":   hit["entity"].get("database_name", "Unknown"),
            "location":      hit["entity"].get("table_name", ""),
            "passage":       hit["entity"].get("raw_ddl", ""),
        })

    if not hits:
        return "No relevant document passages found for this query."

    sections = ["=== DOCUMENT PASSAGES (use these as the ONLY source of truth for your answer) ==="]
    for hit in hits:
        header = f"[Source: {hit['source_file']} | {hit['location']} | Score: {hit['score']:.3f}]"
        sections.append(f"{header}\n{hit['passage']}")

    return "\n\n".join(sections)


@mcp.tool()
def search_exact_fewshot(query: str, threshold: float = 0.95) -> str:
    """
    ALWAYS call this tool FIRST before retrive_schema_rag or any other retrieval.

    Searches the curated few-shot store for an exact semantic match to the user's question.
    Returns a JSON object with:
      - "matched": true  → an exact match was found at or above the similarity threshold
      - "sql": "<query>" → the pre-verified SQL to execute directly

    CRITICAL RULES — you MUST follow these without exception:
    1. If "matched" is true:
       - USE the returned "sql" value DIRECTLY as your final SQL.
       - Do NOT call retrive_schema_rag, get_column_values, or any other tool.
       - Do NOT modify, rephrase, or regenerate the SQL.
       - Immediately execute the SQL and return the results to the user.
    2. If "matched" is false:
       - Proceed to call retrive_schema_rag to retrieve schema context, then generate SQL.
    """
    logger.info(f"search_exact_fewshot query: '{query}' (threshold={threshold})")
    
    if vector_db.provider != "milvus":
        return json.dumps({"matched": False, "error": "Only Milvus supports partitioned few-shot fast path."})

    try:
        emb = embedder.embed(query)
        # L2-normalize to match the unit-norm vectors stored during ingestion
        import math as _math
        _norm = _math.sqrt(sum(x * x for x in emb))
        if _norm > 0:
            emb = [x / _norm for x in emb]
        res = vector_db.client.search(
            collection_name=vector_db.collection,
            data=[emb],
            limit=1,
            output_fields=["database_name", "table_name", "raw_ddl", "embedding_text"],
            partition_names=["few_shot_store"],
        )
        logger.info(f"DEBUG: search_exact_fewshot result: {res}")
        
        if res and res[0]:
            hit = res[0][0]
            dist = float(hit["distance"])
            # Milvus with COSINE metric returns Cosine Distance (1.0 - Cosine Similarity),
            # where 0.0 = identical (similarity 1.0). Convert to similarity in [0, 1].
            score = (1.0 - dist) if (0.0 <= dist <= 1.0) else dist
            logger.info(f"search_exact_fewshot top match score: {score:.4f} (distance: {dist:.4f})")
            
            if score >= threshold:

                raw_ddl = hit["entity"].get("raw_ddl", "")

                # raw_ddl is the full LLM payload: "Question: ...\nSQL:\n<query>\nTables: ..."
                # Extract ONLY the SQL block — everything between "SQL:\n" and the next
                # section header (or end of string). Pass that clean SQL to execute_sql.
                sql = ""
                sql_match = re.search(
                    r"SQL:\n(.*?)(?=\nTables:|\nOutput Columns:|\nRisk Signal:|\nGrain:|\nQuality Notes:|$)",
                    raw_ddl,
                    re.DOTALL,
                )
                if sql_match:
                    sql = sql_match.group(1).strip()
                else:
                    # Fallback: use raw_ddl as-is (shouldn't happen for well-formed records)
                    sql = raw_ddl

                # Strip ap_citizen360. prefix when not in Hive/Iceberg mode
                hive_enabled = os.getenv("HIVE_MCP_ENABLED", "false").strip().lower() in ("true", "1", "yes")
                if not hive_enabled and sql:
                    sql = sql.replace("ap_citizen360.", "")

                logger.info(f"Exact match found! Score: {score:.4f} >= {threshold}")
                logger.info(f"Extracted SQL: {sql[:120]}...")
                return json.dumps({
                    "matched": True,
                    "score": score,
                    "sql": sql
                })
                
    except Exception as e:
        import traceback
        logger.error(f"search_exact_fewshot failed: {e}")
        logger.error(traceback.format_exc())

    return json.dumps({"matched": False})


# =============================================================================
# TEMPORAL CONTEXT TOOL
# =============================================================================

@mcp.tool()
def get_current_date() -> str:
    """
    Returns today's date, the current calendar year, the current financial year
    (April–March), and the current academic year (June–May, Andhra Pradesh school
    calendar).

    Call this tool whenever the user's question contains any relative time
    reference such as:
      - "this year", "current year", "current academic year"
      - "last year", "previous year", "last academic year"
      - "this financial year", "current FY"
      - any question about students without specifying an explicit year

    The `current_academic_year` value (e.g. "2026-27") is the exact string stored
    in the `academic_year` column of the `dim_student` table. Always use this
    value literally in SQL filters — do NOT compute it yourself.

    Example SQL usage:
        WHERE academic_year = '2026-27'
        WHERE academic_year = '2025-26'   -- for "last academic year"
    """
    from datetime import date

    today = date.today()
    year  = today.year
    month = today.month

    # ── Academic year: June–May (AP school calendar) ─────────────────────────
    # If current month >= June → AY is YYYY/(YY+1)  e.g. Aug 2026 → "2026-27"
    # If current month < June  → AY is (YYYY-1)/YY  e.g. Feb 2026 → "2025-26"
    if month >= 6:
        ay_start = year
        ay_end   = year + 1
    else:
        ay_start = year - 1
        ay_end   = year
    current_academic_year = f"{ay_start}-{str(ay_end)[2:]}"       # e.g. "2026-27"
    prev_academic_year    = f"{ay_start - 1}-{str(ay_start)[2:]}" # e.g. "2025-26"

    # ── Financial year: April–March ───────────────────────────────────────────
    if month >= 4:
        fy_start = year
        fy_end   = year + 1
    else:
        fy_start = year - 1
        fy_end   = year
    current_financial_year = f"FY {fy_start}-{str(fy_end)[2:]}"   # e.g. "FY 2026-27"

    result = {
        "today":                   today.isoformat(),            # "2026-08-14"
        "calendar_year":           year,                          # 2026
        "current_academic_year":   current_academic_year,         # "2026-27"  ← use in dim_student SQL
        "previous_academic_year":  prev_academic_year,            # "2025-26"
        "current_financial_year":  current_financial_year,        # "FY 2026-27"
        "note": (
            "For student queries, use `current_academic_year` as the exact value "
            "for the `academic_year` column in dim_student. "
            "The AP academic year runs June–May."
        ),
    }
    logger.info(f"get_current_date called → {result}")
    return json.dumps(result)


if __name__ == "__main__":
    mcp.run(
        transport="stdio",
    )