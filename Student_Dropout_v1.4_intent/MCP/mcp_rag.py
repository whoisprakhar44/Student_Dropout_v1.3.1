try:
    import sys
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

import sys
import logging

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
def load_config():
    path = os.environ.get("RETRIEVAL_CONFIG", "mcp_rag.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


# =========================
# EMBEDDINGS
# =========================
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
            self.url = cfg["embedding"].get(
                "ollama_url",
                "http://localhost:11434/api/embeddings"
            )

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
            uri = cfg["vector_db"]["milvus"]["uri"]
            if not uri.startswith(("http://", "https://")) and not os.path.isabs(uri):
                config_dir = os.path.dirname(
                    os.path.abspath(os.environ.get("RETRIEVAL_CONFIG", "mcp_rag.yaml"))
                )
                uri = os.path.join(config_dir, uri)
            self.client = MilvusClient(uri=uri)
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
            # ── Search schema_store (actual DDL) ─────────────────────────────
            schema_res = self.client.search(
                collection_name=self.collection,
                data=[embedding],
                limit=top_k,
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
                    "score":         1.0 - hit["distance"],
                    "chunk_type":    "schema_ddl",
                }
                for hit in schema_res[0]
            ]

            # ── Search few_shot_store (SQL examples) ─────────────────────────
            try:
                fewshot_res = self.client.search(
                    collection_name=self.collection,
                    data=[embedding],
                    limit=max(1, top_k // 2),
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
                        "score":         1.0 - hit["distance"],
                        "chunk_type":    "few_shot_example",
                    }
                    for hit in fewshot_res[0]
                ]
            except Exception:
                fewshot_hits = []

            # Few-shot examples first (highest semantic signal),
            # then schema DDLs so the LLM sees exact column names after examples.
            return fewshot_hits + schema_hits

        else:
            raise ValueError(f"Unsupported vector_db provider: {self.provider}")

# =========================
# POST PROCESSING
# =========================
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


def threshold(rows: List[Dict], min_score: float = 0.35):
    return [r for r in rows if r["score"] >= min_score]


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
                ddl = ddl.replace("curated_datamodels.", "")
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
                emb_text = emb_text.replace("Database: curated_datamodels", "Database: SQLite")
                emb_text = emb_text.replace("curated_datamodels.", "")
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
            question = r.get("embedding_text", "")
            sql = r.get("raw_ddl", "")
            if question and sql:
                sections.append(f"[Example | score={r['score']:.3f}]\nQuestion: {question}\nSQL:\n{sql}")
            else:
                content = sql or question
                sections.append(f"[Example | score={r['score']:.3f}]\n{content}")

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
if __name__ == "__main__":
    mcp.run(
        transport="stdio",
    )