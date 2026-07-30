from pymilvus import MilvusClient
import json

# use Ollama directly for embedding to match
import requests
resp = requests.post("http://localhost:11434/api/embeddings", json={
    "model": "nomic-embed-text",
    "prompt": "[intent: school_hotspot] which schools in eluru have the highest number of dropouts in 2025 [district: Eluru, year: 2025] [departments: ap_community360]"
})
emb = resp.json()["embedding"]

client = MilvusClient(uri="milvus_schemas.db")
client.load_collection("schema_chunks")

try:
    fewshot_res = client.search(
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
