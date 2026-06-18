import redis
import json
from typing import Any, Optional
from app.config import get_settings

settings = get_settings()

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def set_cache(key: str, value: Any, ttl_seconds: int = 120) -> None:
    get_redis().setex(key, ttl_seconds, json.dumps(value))


def get_cache(key: str) -> Optional[Any]:
    data = get_redis().get(key)
    if data:
        return json.loads(data)
    return None


def delete_cache(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception:
        pass

_JOB_STATUS_TTL = 60 * 60 * 2  # 2 hours


def set_job_status(repo_full_name: str, status: dict) -> None:
    key = f"job:status:{repo_full_name}"
    get_redis().setex(key, _JOB_STATUS_TTL, json.dumps(status))


def get_job_status(repo_full_name: str) -> Optional[dict]:
    key = f"job:status:{repo_full_name}"
    data = get_redis().get(key)
    return json.loads(data) if data else None