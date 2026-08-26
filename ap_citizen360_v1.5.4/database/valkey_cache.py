import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from valkey import Valkey

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logger = logging.getLogger(__name__)

class ValkeyCacheManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ValkeyCacheManager, cls).__new__(cls)
            cls._instance._init()
        return cls._instance
        
    def _init(self):
        # 1. Init Valkey
        valkey_url = os.environ.get("VALKEY_URL", "redis://localhost:6379/0")
        self.valkey = Valkey.from_url(valkey_url, decode_responses=True)
        
        self.threshold = int(os.environ.get("CACHE_HIT_THRESHOLD", "1"))
        self.max_queries = int(os.environ.get("CACHE_MAX_QUERIES", "300"))
        self.semantic_threshold = float(os.environ.get("CACHE_SEMANTIC_THRESHOLD", "0.96"))
        
        self.embedder = None
        self.vector_db = None
        
        # 2. Init Milvus for Semantic Search (Tier 2) - Independent DB
        try:
            import yaml
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(project_root, "config.yaml")
            
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f)
                
            self.embed_provider = cfg.get("embedding", {}).get("provider", "ollama")
            self.embed_model = cfg.get("embedding", {}).get("model", "nomic-embed-text")
            self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/api/embeddings"
            
            if self.embed_provider == "ollama":
                import requests
                self.requests = requests
                
            from pymilvus import MilvusClient
            milvus_path = os.path.join(project_root, "milvus_cache.db")
            self.milvus_client = MilvusClient(uri=milvus_path)
            self.milvus_collection = "cached_queries"
            
            # Ensure collection exists
            if not self.milvus_client.has_collection(self.milvus_collection):
                # Milvus Lite supports basic schema creation implicitly or we define it
                dim = cfg.get("vector_db", {}).get("milvus", {}).get("dim", 768)
                self.milvus_client.create_collection(
                    collection_name=self.milvus_collection,
                    dimension=dim,
                    metric_type="COSINE"
                )
                logger.info(f"Created Milvus cache collection in {milvus_path}")

            # Always load the collection into memory so search() works immediately
            self.milvus_client.load_collection(self.milvus_collection)
            logger.info(f"Milvus cache collection '{self.milvus_collection}' loaded")
        except Exception as e:
            logger.error(f"Failed to init Semantic Cache DB: {e}")
            self.milvus_client = None
            
    def _get_embedding(self, text: str) -> list:
        if self.embed_provider == "ollama":
            res = self.requests.post(
                self.ollama_url,
                json={"model": self.embed_model, "prompt": text}
            )
            return res.json()["embedding"]
        return []
            
    def _hash_query(self, query: str) -> str:
        # Normalize and hash
        normalized = " ".join(query.strip().lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()
        
    def check_cache(self, query: str) -> Optional[Dict[str, Any]]:
        """Tier 1 (Exact) and Tier 2 (Semantic) Check"""
        query_hash = self._hash_query(query)
        exact_key = f"query_cache:{query_hash}"
        
        # Tier 1: Exact Match in Valkey
        try:
            payload_str = self.valkey.get(exact_key)
            if payload_str:
                logger.info(f"Valkey exact match HIT for query: {query}")
                return json.loads(payload_str)
        except Exception as e:
            logger.warning(f"Valkey exact fetch failed: {e}")
            
        # Tier 2: Semantic Match in Milvus
        if self.milvus_client:
            try:
                emb = self._get_embedding(query)
                import math
                norm = math.sqrt(sum(x*x for x in emb))
                if norm > 0:
                    emb = [x/norm for x in emb]
                    
                res = self.milvus_client.search(
                    collection_name=self.milvus_collection,
                    data=[emb],
                    limit=1,
                    output_fields=["raw_ddl", "embedding_text"]
                )
                
                if res and res[0]:
                    hit = res[0][0]
                    dist = float(hit["distance"])
                    score = (dist + 1.0) / 2.0
                    
                    if score >= self.semantic_threshold:
                        logger.info(f"Milvus semantic match HIT (score {score:.3f} >= {self.semantic_threshold}) for query: {query}")
                        payload_str = hit["entity"].get("raw_ddl", "")
                        if payload_str:
                            return json.loads(payload_str)
            except Exception as e:
                logger.error(f"Semantic search failed: {e}")
                
        return None
        
    def record_and_cache(self, query: str, sql: str, department_scope: str, intent: str):
        """Cache every new query immediately. Track hits in ZSET for eviction priority."""
        query_hash = self._hash_query(query)
        hits_key = "query_hits"

        try:
            # Increment hit count in ZSET (used for eviction ordering, not gating)
            current_hits = self.valkey.zincrby(hits_key, 1, query_hash)
            logger.info(f"Query hits for '{query_hash}': {current_hits}")

            # Always cache immediately — no threshold gate
            if True:
                # Store Exact in Valkey
                exact_key = f"query_cache:{query_hash}"
                payload = {
                    "sql": sql,
                    "department_scope": department_scope,
                    "intent": intent,
                    "original_query": query
                }
                self.valkey.set(exact_key, json.dumps(payload))
                logger.info(f"Cached exact query payload to Valkey: {exact_key}")
                
                # Store Semantic in Milvus
                if self.milvus_client:
                    try:
                        emb = self._get_embedding(query)
                        import math
                        norm = math.sqrt(sum(x*x for x in emb))
                        if norm > 0:
                            emb = [x/norm for x in emb]
                            
                        self.milvus_client.insert(
                            collection_name=self.milvus_collection,
                            data=[{
                                "id": int(hashlib.md5(query_hash.encode()).hexdigest()[:15], 16),
                                "vector": emb,
                                "raw_ddl": json.dumps(payload),
                                "embedding_text": query
                            }]
                        )
                        logger.info(f"Cached semantic query payload to Milvus")
                    except Exception as e:
                        logger.error(f"Failed to cache to Milvus: {e}")
                        
            # Enforce Max Queries
            total_cached = self.valkey.zcard(hits_key)
            if total_cached > self.max_queries:
                popped = self.valkey.zpopmin(hits_key, total_cached - self.max_queries)
                for item in popped:
                    evicted_hash = item[0]
                    self.valkey.delete(f"query_cache:{evicted_hash}")
                    logger.info(f"Evicted {evicted_hash} from Valkey cache (max queries reached)")
                    
                    if self.milvus_client:
                        try:
                            evicted_id = int(hashlib.md5(evicted_hash.encode()).hexdigest()[:15], 16)
                            self.milvus_client.delete(
                                collection_name=self.milvus_collection,
                                filter=f"id == {evicted_id}"
                            )
                        except Exception as e:
                            logger.error(f"Failed to evict from Milvus: {e}")
                            
        except Exception as e:
            logger.error(f"Failed to record/cache query: {e}")
