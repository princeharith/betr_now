from __future__ import annotations

import asyncio
import json

from aiokafka import AIOKafkaConsumer

from app.core.config import get_settings

settings = get_settings()


async def consume_bets() -> None:
    consumer = AIOKafkaConsumer(
        settings.kafka_bets_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        # group_id is what makes this a "consumer group" — Kafka remembers,
        # per group, exactly which messages have already been read. Restart
        # this process and it resumes from where it left off, instead of
        # reprocessing the whole topic or missing anything published while
        # it was down.
        group_id="bet-analytics",
        # auto_offset_reset only matters the *first* time this group_id ever
        # connects (no committed offset yet exists for it). "earliest" means
        # start from the very beginning of the topic's history; the default,
        # "latest", would mean only seeing messages published from this
        # point forward, silently ignoring everything already on the topic.
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()

    total_bets = 0
    total_volume = 0.0

    try:
        # This loop runs forever, in a process that has nothing to do with
        # uvicorn or the FastAPI app — it's proof that a consumer can react
        # to the event log completely independently of whatever produced it.
        async for message in consumer:
            event = message.value
            total_bets += 1
            total_volume += event["amount"]
            print(
                f"[bet #{event['bet_id']}] user {event['user_id']} bet "
                f"${event['amount']} on {event['side']} (market {event['market_id']}) "
                f"| running totals: {total_bets} bets, ${total_volume:.2f} volume"
            )
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(consume_bets())
