from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional, Tuple

from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()


@lru_cache()
def get_redis() -> Redis:
    # from_url() doesn't open a connection immediately — redis.asyncio connects
    # lazily on the first actual command, and manages its own connection pool
    # internally. That's why, unlike aiokafka, there's no separate start()/stop().
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _odds_key(market_id: int) -> str:
    # Centralizing the key format in one place avoids typos like "odds:1" vs
    # "odd:1" scattered across the codebase — every caller goes through this.
    return f"odds:{market_id}"


async def cache_odds(market_id: int, yes_price: float, no_price: float) -> None:
    redis = get_redis()
    payload = json.dumps({"yes_price": yes_price, "no_price": no_price})
    await redis.set(_odds_key(market_id), payload)


async def get_cached_odds(market_id: int) -> Optional[Tuple[float, float]]:
    redis = get_redis()
    raw = await redis.get(_odds_key(market_id))
    if raw is None:
        return None
    data = json.loads(raw)
    return data["yes_price"], data["no_price"]


async def publish_odds_update(market_id: int, yes_price: float, no_price: float) -> None:
    # publish() is fire-and-forget: it sends to whoever's subscribed *right now*.
    # If nobody's subscribed yet (no WebSocket clients connected), the message
    # is simply dropped — pub/sub has no memory, unlike Kafka's durable log.
    # That's fine here: this is for *live* updates, not historical replay.
    redis = get_redis()
    channel = f"market:{market_id}:odds"
    payload = json.dumps({"yes_price": yes_price, "no_price": no_price})
    await redis.publish(channel, payload)
