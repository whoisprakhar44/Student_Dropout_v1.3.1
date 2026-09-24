import os
import requests
from dotenv import load_dotenv
from pymilvus import MilvusClient

load_dotenv()

base_url = os.getenv("VLLM_EMBEDDING_BASE_URL", "http://localhost:8005/v1").rstrip("/")
if not base_url.endswith("/v1"):
    base_url = f"{base_url}/v1"

from openai import OpenAI
client = OpenAI(base_url=base_url, api_key=os.getenv("VLLM_EMBEDDING_API_KEY", "EMPTY"))
model = os.getenv("VLLM_EMBEDDING_MODEL", "nomic-embed-text-v1.5")
query_text = "[intent: school_hotspot] which schools in eluru have the highest number of dropouts in 2025 [district: Eluru, year: 2025]"
emb = client.embeddings.create(model=model, input=[query_text]).data[0].embedding

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
