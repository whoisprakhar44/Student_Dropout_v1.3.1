import hashlib
import logging
import os
import json
from typing import Any

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client = None
_redis_checked = False

def get_redis():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    
    _redis_checked = True
    try:
        import redis
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        logger.info(f"[Redis] Connected successfully to {REDIS_URL}")
    except Exception as e:
        logger.warning(f"[Redis] Could not connect to Redis at {REDIS_URL} ({e}). Caching will be disabled.")
        _redis_client = None
    
    return _redis_client


def make_cache_key(prefix: str, text: str) -> str:
    """Generate a deterministic MD5 hash key for Redis."""
    cleaned = text.strip().lower()
    hashed = hashlib.md5(cleaned.encode("utf-8")).hexdigest()
    return f"{prefix}:{hashed}"


def get_cache(key: str) -> str | None:
    """Retrieve string value from Redis cache safely."""
    client = get_redis()
    if not client:
        return None
    try:
        val = client.get(key)
        if val:
            logger.info(f"[Redis] Cache HIT for key: {key}")
        return val
    except Exception as e:
        logger.warning(f"[Redis] Error getting cache key {key}: {e}")
        return None


def set_cache(key: str, value: str, ttl_seconds: int = 3600) -> bool:
    """Set string value in Redis cache safely with TTL (default 1 hr)."""
    client = get_redis()
    if not client:
        return False
    try:
        client.setex(key, ttl_seconds, value)
        logger.info(f"[Redis] Cache SET for key: {key} (TTL: {ttl_seconds}s)")
        return True
    except Exception as e:
        logger.warning(f"[Redis] Error setting cache key {key}: {e}")
        return False


def check_rate_limit(identifier: str, limit: int = 20, window_seconds: int = 60) -> tuple[bool, int]:
    """
    Sliding window rate limiter using Redis ZSET.
    Checks if identifier (username or IP) has exceeded 'limit' requests in 'window_seconds'.
    Returns (is_allowed, remaining_quota).
    """
    import time
    client = get_redis()
    if not client:
        return True, limit

    key = f"ratelimit:{identifier}"
    now = time.time()
    clear_before = now - window_seconds

    try:
        pipeline = client.pipeline()
        pipeline.zremrangebyscore(key, 0, clear_before)
        pipeline.zadd(key, {f"{now}": now})
        pipeline.zcard(key)
        pipeline.expire(key, window_seconds + 2)
        results = pipeline.execute()

        current_count = results[2]
        is_allowed = current_count <= limit
        remaining = max(0, limit - current_count)
        return is_allowed, remaining
    except Exception as e:
        logger.warning(f"[Redis] Rate limit check error for {identifier}: {e}")
        return True, limit
