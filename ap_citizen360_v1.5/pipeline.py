"""
Schema Injection Pipeline
=========================
Modular, config-driven pipeline to:
  1. Read YAML schema files OR a JSONL few-shot file → extract embedding text
  2. Generate embeddings (OpenAI, SentenceTransformers, or Ollama)
  3. Insert into vector DB (ChromaDB local OR Milvus server)

Milvus uses two named partitions inside a single collection:
  • schema_store   – one record per table YAML  (schema pipeline)
  • few_shot_store – NL→SQL exemplars from JSONL (few-shot pipeline)

Field mapping per partition
  Partition        embedding_text   raw_ddl      database_name  table_name
  ─────────────    ──────────────   ───────      ─────────────  ──────────
  schema_store     schema prose     DDL string   DB name        table name
  few_shot_store   NL question      SQL answer   use_case       intent

Usage:
    # inject schemas
    python pipeline.py --config config.yaml
    python pipeline.py --config config.yaml --yaml_dir ./my_yamls

    # inject few-shots
    python pipeline.py --config config.yaml --fewshots school_dropout_fewshots_200.jsonl
"""

import os
import uuid
import logging
import argparse
from pathlib import Path
from typing import Any

from pymilvus import MilvusClient, DataType
import requests
import yaml


# ─────────────────────────────────────────────────────────────────────────────
#  Constants — Milvus partition names
#  Both partitions live inside the SAME collection so a single ANN index
#  covers everything. You can scope queries to one partition at retrieval time.
# ─────────────────────────────────────────────────────────────────────────────

PARTITION_SCHEMA    = "schema_store"     # populated by this pipeline
PARTITION_FEW_SHOT  = "few_shot_store"  # populated later (few-shot injector)


# ─────────────────────────────────────────────────────────────────────────────
#  Config Loader
# ─────────────────────────────────────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# ─────────────────────────────────────────────────────────────────────────────
#  Logger
# ─────────────────────────────────────────────────────────────────────────────

def get_logger(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )
    return logging.getLogger("schema_injection")


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 1 — YAML Reader & Text Extractor
# ─────────────────────────────────────────────────────────────────────────────

def extract_embedding_text(schema: dict) -> str:
    """
    Builds the flat embedding text from a parsed YAML schema dict.
    Order: table → description → columns → business_terms → common_operations
           → sample_values → relationships
    """
    parts = []

    table       = schema.get("table", "")
    database    = schema.get("database", "")
    description = schema.get("description", "")

    parts.append(f"Table {table} in database {database}.")
    if description:
        parts.append(description)

    # Columns
    columns = schema.get("columns", [])
    if columns:
        col_parts = []
        for col in columns:
            name     = col.get("name", "")
            dtype    = col.get("type", "")
            col_desc = col.get("description", "")
            key      = col.get("key", "")
            sample   = col.get("sample_values", [])

            col_str = f"{name} ({dtype}"
            if key:
                col_str += f", {key} key"
            if col_desc:
                col_str += f": {col_desc}"
            if sample:
                col_str += f", e.g. {', '.join(str(s) for s in sample)}"
            col_str += ")"
            col_parts.append(col_str)
        parts.append("Columns: " + "; ".join(col_parts) + ".")

    # Business terms
    biz_terms = schema.get("business_terms", [])
    if biz_terms:
        parts.append("Business concepts: " + ", ".join(biz_terms) + ".")

    # Common operations
    ops = schema.get("common_operations", [])
    if ops:
        parts.append("Common operations: " + ", ".join(ops) + ".")

    # Sample values (top-level)
    sample_values = schema.get("sample_values", {})
    if sample_values:
        sv_parts = [
            f"{col}: {', '.join(str(v) for v in vals)}"
            for col, vals in sample_values.items()
        ]
        parts.append("Sample values — " + "; ".join(sv_parts) + ".")

    # Relationships
    relationships = schema.get("relationships", [])
    if relationships:
        parts.append("Relationships: " + ", ".join(str(r) for r in relationships) + ".")

    return " ".join(parts)


def load_yaml_schemas(yaml_dir: str) -> list[dict]:
    """
    Reads all .yaml / .yml files from yaml_dir (recursive).
    Skips Jupyter checkpoint directories.
    Returns list of dicts:
        { schema, embedding_text, source_file }
    """
    yaml_path = Path(yaml_dir)
    files = [
        fp
        for fp in (
            list(yaml_path.rglob("*.yaml")) +
            list(yaml_path.rglob("*.yml"))
        )
        if ".ipynb_checkpoints" not in fp.parts
    ]

    print(f"[load_yaml_schemas] Found {len(files)} file(s)")
    if not files:
        raise FileNotFoundError(f"No YAML files found in {yaml_dir}")

    records = []
    for fp in files:
        with open(fp, "r") as f:
            schema = yaml.safe_load(f)

        embedding_text = extract_embedding_text(schema)
        records.append({
            "schema":         schema,
            "embedding_text": embedding_text,
            "source_file":    str(fp),
        })

    return records


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 2 — Embedding Generator
# ─────────────────────────────────────────────────────────────────────────────

class EmbeddingGenerator:
    """
    Supports:
      provider: openai              → OpenAI embeddings API
      provider: sentence_transformers → local HuggingFace model
      provider: ollama              → local Ollama server
    """

    def __init__(self, cfg: dict):
        self.provider   = cfg["provider"]
        self.model      = cfg["model"]
        self.batch_size = cfg.get("batch_size", 32)
        self._client    = None

        if self.provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        elif self.provider == "sentence_transformers":
            from sentence_transformers import SentenceTransformer
            self._client = SentenceTransformer(self.model)

        elif self.provider == "ollama":
            self._ollama_url = cfg.get("ollama_url", "http://localhost:11434/api/embeddings")

        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")

    def generate(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings in batches. Returns list of float vectors."""
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch             = texts[i: i + self.batch_size]
            batch_embeddings: list[list[float]] = []

            if self.provider == "openai":
                response = self._client.embeddings.create(
                    model=self.model,
                    input=batch,
                )
                batch_embeddings = [item.embedding for item in response.data]

            elif self.provider == "ollama":
                for text in batch:
                    response = requests.post(
                        self._ollama_url,
                        json={"model": self.model, "prompt": text},
                    )
                    batch_embeddings.append(response.json()["embedding"])

            elif self.provider == "sentence_transformers":
                batch_embeddings = self._client.encode(
                    batch, show_progress_bar=False
                ).tolist()

            all_embeddings.extend(batch_embeddings)

        return all_embeddings


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 3 — Vector DB Client (ChromaDB / Milvus)
# ─────────────────────────────────────────────────────────────────────────────

class VectorDBClient:
    """
    Unified interface for ChromaDB (local) and Milvus (server or Lite).

    Milvus layout
    ─────────────
    Single collection  →  two named partitions
        schema_store      one doc per table YAML   ← this pipeline writes here
        few_shot_store    NL→SQL exemplars          ← injected separately later

    Why partitions instead of separate collections?
      • A single HNSW/FLAT index covers all vectors — no duplicated index cost.
      • At query time you can search ALL data or scope to one partition.
      • The schema is identical for both partitions which keeps things DRY.
    """

    def __init__(self, cfg: dict):
        self.provider        = cfg["provider"]
        self._collection     = None   # ChromaDB collection handle
        self._client         = None   # MilvusClient handle
        self._collection_name: str | None = None

        if self.provider == "chromadb":
            self._init_chromadb(cfg["chromadb"])

        elif self.provider == "milvus":
            self._init_milvus(cfg["milvus"])

        else:
            raise ValueError(f"Unsupported vector DB provider: {self.provider}")

    # ── ChromaDB ──────────────────────────────────────────────────────────────

    def _init_chromadb(self, cfg: dict):
        import chromadb

        mode            = cfg.get("mode", "persistent")
        collection_name = cfg.get("collection", "schema_chunks")

        if mode == "persistent":
            client = chromadb.PersistentClient(path=cfg["path"])
        else:
            client = chromadb.EphemeralClient()

        self._collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Milvus ────────────────────────────────────────────────────────────────

    def _init_milvus(self, cfg: dict):
        uri                   = cfg["uri"]
        self._collection_name = cfg.get("collection", "schema_chunks")
        dim                   = cfg.get("dim", 768)
        metric_type           = cfg.get("metric_type", "COSINE")

        # ── Connect ──────────────────────────────────────────────────────────
        # MilvusClient(uri) works for both:
        #   "./milvus_schemas.db"  → Milvus Lite  (local .db file)
        #   "http://host:19530"    → Milvus Standalone / Distributed
        self._client = MilvusClient(uri=uri)

        # ── Collection already exists → ensure both partitions exist ─────────
        if self._client.has_collection(self._collection_name):
            self._ensure_partitions()
            return

        # ── Schema ───────────────────────────────────────────────────────────
        # Unchanged from your original file — 7 fields exactly.
        # Partition isolation is handled by Milvus named partitions,
        # NOT by an extra field in the schema.

        schema = MilvusClient.create_schema(
            auto_id=False,              # we provide IDs ourselves
            enable_dynamic_field=False, # strict schema, no extra fields
        )

        schema.add_field(
            field_name="id",
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=64,              # UUID string length
        )
        schema.add_field(
            field_name="database_name",
            datatype=DataType.VARCHAR,
            max_length=256,
        )
        schema.add_field(
            field_name="table_name",
            datatype=DataType.VARCHAR,
            max_length=256,
        )
        schema.add_field(
            field_name="embedding_text",
            datatype=DataType.VARCHAR,
            max_length=10000,           # full embedding text string
        )
        schema.add_field(
            field_name="raw_ddl",
            datatype=DataType.VARCHAR,
            max_length=65535,           # raw DDL can be very long (largest seen: ~11k chars)
        )
        schema.add_field(
            field_name="source_file",
            datatype=DataType.VARCHAR,
            max_length=512,
        )
        schema.add_field(
            field_name="embedding",
            datatype=DataType.FLOAT_VECTOR,
            dim=dim,                    # must match your embedding model (e.g. 768 for nomic)
        )

        # ── Index ─────────────────────────────────────────────────────────────
        # Defined BEFORE create_collection so schema + index are set together.
        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="FLAT",
            metric_type=metric_type,
        )

        # ── Create collection with partitions enabled ─────────────────────────
        self._client.create_collection(
            collection_name=self._collection_name,
            schema=schema,
            index_params=index_params,
        )

        # ── Create named partitions ───────────────────────────────────────────
        self._ensure_partitions()

    def _ensure_partitions(self):
        """Idempotently create the two named partitions if they don't exist."""
        for partition_name in (PARTITION_SCHEMA, PARTITION_FEW_SHOT):
            if not self._client.has_partition(
                collection_name=self._collection_name,
                partition_name=partition_name,
            ):
                self._client.create_partition(
                    collection_name=self._collection_name,
                    partition_name=partition_name,
                )

    # ── Unified Insert ────────────────────────────────────────────────────────

    def insert(self, records: list[dict], partition: str = PARTITION_SCHEMA):
        """
        Insert records into the vector DB.

        Args:
            records:   Each dict must have the 7 core fields + embedding:
                         id, database_name, table_name,
                         embedding_text, raw_ddl, source_file, embedding
            partition: Milvus partition name (default: PARTITION_SCHEMA).
                       Ignored for ChromaDB.
        """
        if self.provider == "chromadb":
            self._insert_chromadb(records)
        elif self.provider == "milvus":
            self._insert_milvus(records, partition)

    def _insert_chromadb(self, records: list[dict]):
        self._collection.upsert(
            ids=[r["id"] for r in records],
            embeddings=[r["embedding"] for r in records],
            documents=[r["embedding_text"] for r in records],
            metadatas=[
                {
                    "database_name": r["database_name"],
                    "table_name":    r["table_name"],
                    "raw_ddl":       r["raw_ddl"],
                    "source_file":   r["source_file"],
                }
                for r in records
            ],
        )

    def _insert_milvus(self, records: list[dict], partition: str):
        data = [
            {
                "id":             r["id"],
                "database_name":  r["database_name"],
                "table_name":     r["table_name"],
                "embedding_text": r["embedding_text"],
                "raw_ddl":        r["raw_ddl"],
                "source_file":    r["source_file"],
                "embedding":      r["embedding"],
            }
            for r in records
        ]

        # upsert into the named partition — handles duplicate re-runs cleanly.
        # MilvusClient auto-persists; no explicit flush() needed.
        self._client.upsert(
            collection_name=self._collection_name,
            partition_name=partition,
            data=data,
        )

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(
        self,
        embedding: list[float],
        top_k: int = 5,
        partition: str | None = None,
    ) -> list[dict]:
        """
        Semantic search.

        Args:
            embedding:  Query vector.
            top_k:      Number of results.
            partition:  Milvus partition to scope the search to.
                        Pass None to search across ALL partitions.
        """
        if self.provider == "chromadb":
            return self._query_chromadb(embedding, top_k)
        elif self.provider == "milvus":
            return self._query_milvus(embedding, top_k, partition)

    def _query_chromadb(self, embedding: list[float], top_k: int) -> list[dict]:
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return [
            {
                "table_name":    results["metadatas"][0][i]["table_name"],
                "database_name": results["metadatas"][0][i]["database_name"],
                "raw_ddl":       results["metadatas"][0][i]["raw_ddl"],
                "score":         results["distances"][0][i],
            }
            for i in range(len(results["ids"][0]))
        ]

    def _query_milvus(
        self,
        embedding: list[float],
        top_k: int,
        partition: str | None,
    ) -> list[dict]:
        search_kwargs: dict[str, Any] = {
            "collection_name": self._collection_name,
            "data":            [embedding],
            "limit":           top_k,
            "output_fields":   [
                "table_name",
                "database_name",
                "raw_ddl",
                "embedding_text",
            ],
            "search_params": {
                "metric_type": "COSINE",
            },
        }
        if partition:
            search_kwargs["partition_names"] = [partition]

        results = self._client.search(**search_kwargs)

        return [
            {
                "table_name":     hit["entity"]["table_name"],
                "database_name":  hit["entity"]["database_name"],
                "raw_ddl":        hit["entity"]["raw_ddl"],
                "embedding_text": hit["entity"]["embedding_text"],
                "score":          hit["distance"],
            }
            for hit in results[0]
        ]


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 4 — Record Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_schema_records(
    yaml_records: list[dict],
    embeddings: list[list[float]],
) -> list[dict]:
    """
    Combines YAML data + embeddings into insertable records for schema_store.
    Schema matches the original exactly — 7 fields + embedding.
    Few-shot records will be built by a separate injector when those arrive.
    """
    records = []
    for yr, emb in zip(yaml_records, embeddings):
        schema = yr["schema"]
        record = {
            "id":             str(uuid.uuid4()),
            "database_name":  schema.get("database", ""),
            "table_name":     schema.get("table", ""),
            "embedding_text": yr["embedding_text"],
            "raw_ddl":        schema.get("raw_ddl", ""),
            "source_file":    yr["source_file"],
            "embedding":      emb,
        }
        records.append(record)
    return records


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(config_path: str, yaml_dir_override: str | None = None):
    cfg    = load_config(config_path)
    logger = get_logger(cfg.get("logging", {}).get("level", "INFO"))

    yaml_dir = yaml_dir_override or cfg.get("yaml_dir", "./schema_yamls")

    # Step 1 — Load YAMLs
    logger.info(f"Loading YAML schemas from: {yaml_dir}")
    yaml_records = load_yaml_schemas(yaml_dir)
    logger.info(f"Loaded {len(yaml_records)} schema YAML(s)")

    # Step 2 — Generate embeddings
    logger.info(
        f"Generating embeddings using "
        f"{cfg['embedding']['provider']} / {cfg['embedding']['model']}"
    )
    embedder   = EmbeddingGenerator(cfg["embedding"])
    texts      = [r["embedding_text"] for r in yaml_records]
    embeddings = embedder.generate(texts)
    logger.info(f"Generated {len(embeddings)} embedding(s)")

    # Step 3 — Init vector DB (creates collection + partitions on first run)
    logger.info(f"Connecting to vector DB: {cfg['vector_db']['provider']}")
    vdb = VectorDBClient(cfg["vector_db"])

    # Step 4 — Build and insert into schema_store partition
    records = build_schema_records(yaml_records, embeddings)
    vdb.insert(records, partition=PARTITION_SCHEMA)
    logger.info(
        f"Inserted {len(records)} record(s) into "
        f"partition '{PARTITION_SCHEMA}'"
    )

    return records


# ─────────────────────────────────────────────────────────────────────────────
#  FEW-SHOT PIPELINE  (schema_store sibling — writes to few_shot_store)
# ─────────────────────────────────────────────────────────────────────────────

import json


def load_fewshot_records(jsonl_path: str) -> list[dict]:
    """
    Reads the JSONL few-shot file.
    Each line must contain at minimum: id, question, sql.
    Optional metadata fields (use_case, intent, topic, etc.) are preserved
    in database_name / table_name for downstream filtering.

    Field mapping  →  Milvus field
    ─────────────────────────────────────────────────────
    question       →  embedding_text   (what gets embedded)
    sql            →  raw_ddl          (gold answer stored alongside)
    use_case       →  database_name    (reused for domain tagging)
    intent         →  table_name       (reused for intent tagging)
    id (original)  →  source_file      (provenance — keeps the JSONL row id)
    """
    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            records.append({
                "source_id":      row.get("id", ""),
                "embedding_text": row["question"],      # NL question → embedded
                "raw_ddl":        row["sql"],            # gold SQL stored as-is
                "database_name":  row.get("use_case", ""),
                "table_name":     row.get("intent", ""),
                "source_file":    jsonl_path,
            })
    return records


def build_fewshot_records(
    raw_records: list[dict],
    embeddings: list[list[float]],
) -> list[dict]:
    """
    Pairs loaded JSONL rows with their embeddings.
    Produces dicts that match the exact 7-field Milvus schema:
        id, database_name, table_name, embedding_text, raw_ddl, source_file, embedding
    """
    records = []
    for row, emb in zip(raw_records, embeddings):
        record = {
            "id":             str(uuid.uuid4()),   # new UUID per insertion
            "database_name":  row["database_name"],
            "table_name":     row["table_name"],
            "embedding_text": row["embedding_text"],
            "raw_ddl":        row["raw_ddl"],
            "source_file":    row["source_file"],
            "embedding":      emb,
        }
        records.append(record)
    return records


def run_fewshot_pipeline(config_path: str, jsonl_path: str):
    """
    Injects few-shot NL→SQL pairs from a JSONL file into the
    few_shot_store partition of the same Milvus collection.

    Args:
        config_path: Path to config.yaml (same file used for schema pipeline).
        jsonl_path:  Path to the .jsonl few-shot file.
    """
    cfg    = load_config(config_path)
    logger = get_logger(cfg.get("logging", {}).get("level", "INFO"))

    # Step 1 — Load JSONL
    logger.info(f"Loading few-shots from: {jsonl_path}")
    raw_records = load_fewshot_records(jsonl_path)
    logger.info(f"Loaded {len(raw_records)} few-shot record(s)")

    # Step 2 — Embed the NL questions
    logger.info(
        f"Generating embeddings using "
        f"{cfg['embedding']['provider']} / {cfg['embedding']['model']}"
    )
    embedder   = EmbeddingGenerator(cfg["embedding"])
    texts      = [r["embedding_text"] for r in raw_records]
    embeddings = embedder.generate(texts)
    logger.info(f"Generated {len(embeddings)} embedding(s)")

    # Step 3 — Init vector DB (creates collection + partitions if needed)
    logger.info(f"Connecting to vector DB: {cfg['vector_db']['provider']}")
    vdb = VectorDBClient(cfg["vector_db"])

    # Step 4 — Build and insert into few_shot_store partition
    records = build_fewshot_records(raw_records, embeddings)
    vdb.insert(records, partition=PARTITION_FEW_SHOT)
    logger.info(
        f"Inserted {len(records)} record(s) into "
        f"partition '{PARTITION_FEW_SHOT}'"
    )

    return records


# ─────────────────────────────────────────────────────────────────────────────
#  CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schema / Few-shot Injection Pipeline")
    parser.add_argument("--config",   default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--yaml_dir", default=None,
                        help="Override yaml_dir from config (schema pipeline)")
    parser.add_argument("--fewshots", default=None,
                        help="Path to .jsonl few-shot file — runs the few-shot pipeline instead")
    args = parser.parse_args()

    if args.fewshots:
        run_fewshot_pipeline(args.config, args.fewshots)
    else:
        run_pipeline(args.config, args.yaml_dir)
