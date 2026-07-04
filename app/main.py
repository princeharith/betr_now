from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import bets, markets, settlement, users, websocket
from app.services.kafka_producer import start_producer, stop_producer


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Runs once, when the app starts — before it accepts any requests.
    # This is where the Kafka producer opens its connection (see
    # kafka_producer.py: aiokafka needs an explicit start()/stop(), unlike
    # Redis, which connects lazily on first use and needs no lifespan hook).
    await start_producer()
    yield
    # Runs once, when the app is shutting down — after it stops accepting
    # new requests. Flushes any buffered Kafka messages before exiting.
    await stop_producer()


app = FastAPI(title="SideBet", lifespan=lifespan)

# Browsers block cross-origin requests by default (a request from the future
# React frontend, on a different port than this API, counts as "cross-origin").
# CORSMiddleware explicitly allows it. allow_origins=["*"] is fine for local
# development; this should be tightened to a specific domain before any real
# deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(markets.router)
app.include_router(bets.router)
app.include_router(websocket.router)
app.include_router(settlement.router)

# Auto-instruments every route with request count/latency metrics and exposes
# them at GET /metrics, in the format Prometheus expects to scrape.
Instrumentator().instrument(app).expose(app)
