import os
import requests
from dotenv import load_dotenv
from pymilvus import MilvusClient

load_dotenv()

emb_provider = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()
query_text = "[intent: school_hotspot] which schools in eluru have the highest number of dropouts in 2025 [district: Eluru, year: 2025]"

if emb_provider == "vllm":
    from openai import OpenAI
    base_url = os.getenv("VLLM_EMBEDDING_BASE_URL", "http://localhost:8005/v1").rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    client = OpenAI(base_url=base_url, api_key=os.getenv("VLLM_EMBEDDING_API_KEY", "EMPTY"))
    model = os.getenv("VLLM_EMBEDDING_MODEL", "nomic-embed-text-v1.5")
    emb = client.embeddings.create(model=model, input=[query_text]).data[0].embedding
else:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    resp = requests.post(f"{base_url}/api/embeddings", json={
        "model": model,
        "prompt": query_text
    })
    emb = resp.json()["embedding"]

milvus_client = MilvusClient(uri="milvus_schemas.db")
milvus_client.load_collection("schema_chunks")

try:
    fewshot_res = milvus_client.search(
        collection_name="schema_chunks",
        data=[emb],
        limit=2,
        output_fields=["database_name", "table_name", "raw_ddl", "embedding_text"],
        search_params={"metric_type": "COSINE"},
        partition_names=["few_shot_store"],
    )
    print("fewshot_res hits:", len(fewshot_res[0]))
    for hit in fewshot_res[0]:
        print("hit distance:", hit["distance"], "score:", 1.0 - hit["distance"])
except Exception as e:
    import traceback
    traceback.print_exc()
