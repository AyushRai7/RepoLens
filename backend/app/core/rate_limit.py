from app.db.cache import get_redis


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Returns False once the caller has exceeded max_requests within window_seconds."""
    import time
    redis_key = f"ratelimit:{key}:{int(time.time() // window_seconds)}"
    r = get_redis()
    current = r.incr(redis_key)
    if current == 1:
        r.expire(redis_key, window_seconds)
    return current <= max_requests


def get_ws_client_ip(websocket) -> str:
    """
    Prefer X-Forwarded-For when present — once you deploy behind Railway/
    Vercel/any reverse proxy, websocket.client.host will be the proxy's
    internal IP, not the real visitor, unless you read this header instead.
    """
    forwarded = websocket.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return websocket.client.host if websocket.client else "unknown"