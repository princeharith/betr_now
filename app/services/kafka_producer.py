from __future__ import annotations

import json
from typing import Optional

from aiokafka import AIOKafkaProducer

from app.core.config import get_settings

settings = get_settings()

_producer: Optional[AIOKafkaProducer] = None


async def start_producer() -> None:
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        # Kafka only transmits raw bytes. value_serializer runs automatically on
        # every message passed to send()/send_and_wait(), so callers can just
        # pass a plain Python dict instead of manually encoding JSON every time.
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await _producer.start()  # opens the actual TCP connection to the Kafka broker


async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        # aiokafka buffers messages internally and sends them in batches for
        # efficiency. stop() flushes anything still buffered before closing the
        # connection — skip this and unsent messages are silently lost on shutdown.
        await _producer.stop()
        _producer = None


async def publish_bet_event(event: dict) -> None:
    if _producer is None:
        # Bets are already durably written to Postgres by the time this is called
        # (see the route in bets.py). Kafka is for notifying other services, so a
        # missing producer shouldn't corrupt the bet itself — but it should be loud,
        # not silent, so you notice during development if start_producer() was
        # never called (e.g. forgot to wire it into main.py's lifespan).
        raise RuntimeError("Kafka producer not started — call start_producer() first")

    await _producer.send_and_wait(settings.kafka_bets_topic, value=event)
