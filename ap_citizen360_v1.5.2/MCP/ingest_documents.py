"""
ingest_documents.py
-------------------
One-time / batch ingestion pipeline for unstructured documents.

Supported formats: PDF (.pdf), Word (.docx), Plain text (.txt)

Usage:
    # Ingest all documents in the default documents/ directory
    python MCP/ingest_documents.py

    # Ingest from a custom directory
    python MCP/ingest_documents.py --doc_dir /path/to/documents

    # Dry-run (parse + chunk only, no Milvus write)
    python MCP/ingest_documents.py --dry_run

Strategy:
    1. Parse: Extract raw text + metadata (filename, page/section) per document
    2. Chunk: Sliding-window, 1000 chars with 200-char overlap
       - For PDFs: detect likely headings via font size and inject as chunk prefix
       - For DOCX: use paragraph styles to detect headings
       - For TXT:  no heading detection; plain chunking only
    3. Embed: Use existing Ollama nomic-embed-text (768-dim) from mcp_rag.yaml
    4. Store: Insert into Milvus 'document_store' partition in schema_chunks collection

Milvus field mapping for document_store:
    embedding_text → chunk text (used for vector similarity)
    raw_ddl        → chunk text with header prefix (given verbatim to LLM)
    database_name  → source filename (for citation)
    table_name     → location label e.g. "Page 12" or "Section 3" (for citation)
"""

import argparse
import logging
import os
import sys
import uuid

import requests
import yaml

# ---------------------------------------------------------------------------
# Resolve project root so we can import MCP configs from anywhere
# ---------------------------------------------------------------------------
MCP_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(MCP_DIR)
CONFIG_PATH  = os.path.join(MCP_DIR, "mcp_rag.yaml")
DEFAULT_DOC_DIR = os.path.join(PROJECT_ROOT, "documents")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ingest_documents")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# STEP 1 — Parsers
# ---------------------------------------------------------------------------

def _parse_pdf(file_path: str) -> list[dict]:
    """
    Extract text from a PDF file page by page.
    Attempts heading detection via font size — the largest font on a page
    (above 11pt and bold) is treated as a section heading and injected
    as context into every chunk from that page.

    Returns a list of dicts:
        { "text": str, "page": int, "heading": str | None }
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed. Run: pip install PyMuPDF")
        sys.exit(1)

    pages = []
    doc = fitz.open(file_path)

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        text_parts = []
        heading_candidate = None
        max_font_size = 0.0

        for block in blocks:
            if block.get("type") != 0:  # 0 = text block
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "").strip()
                    if not span_text:
                        continue
                    text_parts.append(span_text)

                    # Heading detection: large bold text that spans < 120 chars
                    size  = span.get("size", 0)
                    flags = span.get("flags", 0)
                    is_bold = bool(flags & 2**4)  # bit 4 = bold in PyMuPDF
                    if (
                        size > max_font_size
                        and size > 11
                        and is_bold
                        and len(span_text) < 120
                    ):
                        max_font_size = size
                        heading_candidate = span_text

        page_text = " ".join(text_parts).strip()
        if page_text:
            pages.append({
                "text": page_text,
                "page": page_num,
                "heading": heading_candidate,
            })

    doc.close()
    logger.info("PDF '%s': extracted %d pages", os.path.basename(file_path), len(pages))
    return pages


def _parse_docx(file_path: str) -> list[dict]:
    """
    Extract paragraphs from a DOCX file.
    Heading-style paragraphs (Word built-in 'Heading N') are tracked and
    injected as section context into subsequent content chunks.

    Returns a list of dicts:
        { "text": str, "section": int, "heading": str | None }
    """
    try:
        from docx import Document
    except ImportError:
        logger.error("python-docx not installed. Run: pip install python-docx")
        sys.exit(1)

    doc = Document(file_path)
    paragraphs = []
    current_heading = None
    section_num = 1

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = (para.style.name or "").lower()

        # Detect heading styles (Heading 1, Heading 2, etc.)
        if "heading" in style_name:
            current_heading = text
            section_num += 1
            # Don't add headings as standalone items — they prefix the next content
            continue

        paragraphs.append({
            "text": text,
            "section": section_num,
            "heading": current_heading,
        })

    logger.info("DOCX '%s': extracted %d paragraphs", os.path.basename(file_path), len(paragraphs))
    return paragraphs


def _parse_txt(file_path: str) -> list[dict]:
    """
    Read a plain text file and split into logical line groups.
    No heading detection for TXT (format too varied).

    Returns a list of dicts: { "text": str }
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Split on blank lines to form paragraph-like groups
    raw_groups = [g.strip() for g in content.split("\n\n") if g.strip()]
    segments   = [{"text": g} for g in raw_groups]

    logger.info("TXT '%s': extracted %d segments", os.path.basename(file_path), len(segments))
    return segments


# ---------------------------------------------------------------------------
# STEP 2 — Chunking
# ---------------------------------------------------------------------------

CHUNK_SIZE    = 1000   # characters
CHUNK_OVERLAP = 200    # overlap between consecutive chunks


def _sliding_chunks(text: str) -> list[str]:
    """Yield overlapping fixed-size character chunks."""
    if not text:
        return []
    chunks = []
    start  = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def build_chunks(segments: list[dict], filename: str) -> list[dict]:
    """
    Convert parsed document segments into Milvus-ready chunk dicts.
    Each chunk carries:
        embedding_text  → chunk text (plain, for vector embedding)
        raw_ddl         → header-prefixed chunk text (given verbatim to LLM)
        database_name   → source filename
        table_name      → location label (e.g. "Page 12")
    """
    chunks = []
    for seg in segments:
        text    = seg.get("text", "")
        heading = seg.get("heading")

        # Location label for citations
        if "page" in seg:
            location = f"Page {seg['page']}"
        elif "section" in seg:
            location = f"Section {seg['section']}"
        else:
            location = "Document"

        for raw_chunk in _sliding_chunks(text):
            # embedding_text: plain chunk → clean semantic signal for vector search
            embedding_text = raw_chunk.strip()

            # raw_ddl: heading-prefixed version → richer context for the LLM
            if heading:
                context_prefix = f"[{filename} | {location} | Section: {heading}]\n"
            else:
                context_prefix = f"[{filename} | {location}]\n"

            raw_content = context_prefix + raw_chunk.strip()

            chunks.append({
                "embedding_text": embedding_text,
                "raw_ddl":        raw_content,
                "database_name":  filename,
                "table_name":     location,
            })

    return chunks


# ---------------------------------------------------------------------------
# STEP 3 — Embedder
# ---------------------------------------------------------------------------

class OllamaEmbedder:
    """Thin Ollama embedding client — reuses same setup as mcp_rag.py."""

    def __init__(self, cfg: dict):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.url   = f"{base_url}/api/embeddings"
        self.model = cfg["embedding"]["model"]

    def embed(self, text: str) -> list[float]:
        resp = requests.post(
            self.url,
            json={"model": self.model, "prompt": text},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]


# ---------------------------------------------------------------------------
# STEP 4 — Milvus Writer
# ---------------------------------------------------------------------------

PARTITION_DOCS = "document_store"


def _ensure_partition(client, collection: str) -> None:
    """Create the document_store partition if it does not already exist."""
    existing = client.list_partitions(collection)
    # Some older pymilvus versions return objects, handle both
    existing_names = [p if isinstance(p, str) else p.partition_name for p in existing]
    if PARTITION_DOCS not in existing_names:
        client.create_partition(collection, partition_name=PARTITION_DOCS)
        logger.info("Created Milvus partition '%s'", PARTITION_DOCS)
    else:
        logger.info("Milvus partition '%s' already exists", PARTITION_DOCS)


def insert_chunks(client, collection: str, chunks: list[dict], embedder: OllamaEmbedder, dry_run: bool) -> int:
    """Embed + insert chunks into Milvus document_store partition."""
    if not chunks:
        return 0

    records = []
    for i, chunk in enumerate(chunks):
        emb_text = chunk["embedding_text"]
        if not emb_text.strip():
            continue

        if dry_run:
            logger.info("[DRY RUN] Would embed chunk %d/%d: %s...", i + 1, len(chunks), emb_text[:60])
            continue

        embedding = embedder.embed(emb_text)
        records.append({
            "id":             str(uuid.uuid4()).replace("-", ""),
            "embedding":      embedding,
            "embedding_text": chunk["embedding_text"],
            "raw_ddl":        chunk["raw_ddl"],
            "database_name":  chunk["database_name"],
            "table_name":     chunk["table_name"],
            "source_file":    chunk["database_name"], # Required by schema
        })

    if dry_run:
        return len(chunks)

    if records:
        client.insert(
            collection_name=collection,
            data=records,
            partition_name=PARTITION_DOCS,
        )
        logger.info("Inserted %d chunks into partition '%s'", len(records), PARTITION_DOCS)

    return len(records)


# ---------------------------------------------------------------------------
# STEP 5 — Milvus connection helper
# ---------------------------------------------------------------------------

def _build_milvus_client(cfg: dict):
    from pymilvus import MilvusClient

    uri = cfg["vector_db"]["milvus"]["uri"]
    if not uri.startswith(("http://", "https://")) and not os.path.isabs(uri):
        uri = os.path.normpath(os.path.join(MCP_DIR, uri))

    client = MilvusClient(uri=uri)
    return client


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ingest PDF/DOCX/TXT documents into Milvus.")
    parser.add_argument("--doc_dir", default=DEFAULT_DOC_DIR, help="Directory containing documents to ingest")
    parser.add_argument("--dry_run", action="store_true", help="Parse and chunk only — no Milvus writes")
    args = parser.parse_args()

    doc_dir = os.path.abspath(args.doc_dir)
    if not os.path.isdir(doc_dir):
        logger.error("Document directory not found: %s", doc_dir)
        sys.exit(1)

    # Collect supported files recursively
    supported_exts = {".pdf", ".docx", ".txt"}
    doc_files = []
    for root, _, files in os.walk(doc_dir):
        for fname in files:
            if os.path.splitext(fname)[1].lower() in supported_exts:
                doc_files.append(os.path.join(root, fname))

    if not doc_files:
        logger.warning("No PDF/DOCX/TXT files found in: %s", doc_dir)
        return

    logger.info("Found %d document(s) to ingest: %s", len(doc_files), [os.path.basename(f) for f in doc_files])

    cfg      = load_config()
    embedder = OllamaEmbedder(cfg)

    # Milvus setup
    if not args.dry_run:
        client     = _build_milvus_client(cfg)
        collection = cfg["vector_db"]["milvus"]["collection"]
        _ensure_partition(client, collection)
    else:
        client     = None
        collection = None
        logger.info("DRY RUN mode — no Milvus writes will occur")

    total_chunks = 0

    for file_path in doc_files:
        filename = os.path.basename(file_path)
        ext      = os.path.splitext(filename)[1].lower()
        logger.info("Processing: %s", filename)

        try:
            if ext == ".pdf":
                segments = _parse_pdf(file_path)
            elif ext == ".docx":
                segments = _parse_docx(file_path)
            elif ext == ".txt":
                segments = _parse_txt(file_path)
            else:
                logger.warning("Skipping unsupported file: %s", filename)
                continue
        except Exception as e:
            logger.error("Failed to parse '%s': %s", filename, e)
            continue

        chunks = build_chunks(segments, filename)
        logger.info("  → %d chunks from %s", len(chunks), filename)

        if args.dry_run:
            for i, c in enumerate(chunks[:3]):
                logger.info("  [Sample chunk %d] %s...", i + 1, c["raw_ddl"][:120])
        else:
            inserted = insert_chunks(client, collection, chunks, embedder, dry_run=False)
            total_chunks += inserted

    if not args.dry_run:
        logger.info("=== Ingestion complete: %d total chunks inserted across %d documents ===", total_chunks, len(doc_files))
    else:
        logger.info("=== Dry run complete. No data written to Milvus ===")


if __name__ == "__main__":
    main()
