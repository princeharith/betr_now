from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- User ----------

class UserCreate(BaseModel):
    username: str
    display_name: str = Field(max_length=10)
    # TODO: any validation? e.g. min/max length on username?


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # lets this read directly from an ORM object

    id: int
    username: str
    display_name: str
    balance: float
    created_at: datetime


# ---------- Market ----------

class MarketCreate(BaseModel):
    title: str
    description: Optional[str] = None
    creator_id: int
    resolve_at: Optional[datetime] = None
    # TODO: should a client be able to set starting pool sizes, or always default?


class MarketResolve(BaseModel):
    # Same Literal trick you used on BetCreate.side — rejects anything
    # that isn't exactly "yes" or "no" before the route code ever runs.
    outcome: Literal["yes", "no"]


class MarketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    creator_id: int
    status: str
    pool_yes: float
    pool_no: float
    outcome: Optional[str] = None
    resolve_at: Optional[datetime]
    created_at: datetime
    # TODO: want to include computed yes_price/no_price here too? (not a DB column —
    # would need a Pydantic @computed_field or just calculate it in the route)


# ---------- Bet ----------

class BetCreate(BaseModel):
    user_id: int
    market_id: int
    side: Literal["yes", "no"]  # TODO: restrict to "yes"/"no" at this layer too? look up Pydantic's Literal type
    amount: float


class BetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    market_id: int
    side: str
    amount: float
    shares: float
    price: float
    created_at: datetime


# ---------- Position ----------

class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    market_id: int
    side: str
    shares: float
    avg_price: float
