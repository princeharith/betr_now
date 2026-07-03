from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.redis_service import get_cached_odds, get_redis

router = APIRouter()


@router.websocket("/ws/markets/{market_id}")
async def market_odds_feed(websocket: WebSocket, market_id: int) -> None:
    # Unlike a normal HTTP route, a WebSocket connection stays open. accept()
    # completes the handshake; after this, it's a two-way pipe until either
    # side closes it.
    await websocket.accept()

    # Send whatever we already know immediately, so a client doesn't have to
    # wait for the *next* bet just to see the current odds.
    cached = await get_cached_odds(market_id)
    if cached is not None:
        yes_price, no_price = cached
        await websocket.send_json({"yes_price": yes_price, "no_price": no_price})

    # Subscribe to this market's Redis channel — the other end of
    # publish_odds_update() in redis_service.py.
    redis = get_redis()
    pubsub = redis.pubsub()
    channel = f"market:{market_id}:odds"
    await pubsub.subscribe(channel)

    try:
        # pubsub.listen() is an async generator: it suspends here doing
        # nothing until a message arrives on the channel, then yields it,
        # then suspends again. This loop is what makes the connection
        # "live" — no polling, just reacting whenever Redis has something.
        async for message in pubsub.listen():
            if message["type"] != "message":
                # subscribe/unsubscribe confirmations flow through this same
                # stream — skip anything that isn't an actual published update.
                continue
            await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        # The client closed their tab / lost connection — expected, not an error.
        pass
    finally:
        # Always clean up the subscription, even on an unclean disconnect —
        # otherwise this subscription leaks for the life of the Redis connection.
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
