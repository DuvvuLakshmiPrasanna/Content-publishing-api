import json
from typing import Optional
import redis
from app.config import get_settings

settings = get_settings()

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

CACHE_TTL = 300  # 5 minutes


def get_cache(key: str) -> Optional[str]:
    try:
        return redis_client.get(key)
    except redis.RedisError:
        return None


def set_cache(key: str, value: str, ttl: int = CACHE_TTL):
    try:
        redis_client.setex(key, ttl, value)
    except redis.RedisError:
        pass


def delete_cache(key: str):
    try:
        redis_client.delete(key)
    except redis.RedisError:
        pass


def invalidate_published_cache():
    """Invalidate all published post cache entries."""
    try:
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="published:*", count=100)
            if keys:
                redis_client.delete(*keys)
            if cursor == 0:
                break
    except redis.RedisError:
        pass


def invalidate_post_cache(post_id: int):
    """Invalidate cache for a specific post."""
    delete_cache(f"published:post:{post_id}")
    invalidate_list_cache()


def invalidate_list_cache():
    """Invalidate all list/search caches."""
    try:
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="published:list:*", count=100)
            if keys:
                redis_client.delete(*keys)
            if cursor == 0:
                break
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="search:*", count=100)
            if keys:
                redis_client.delete(*keys)
            if cursor == 0:
                break
    except redis.RedisError:
        pass
