from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    balance: Mapped[float] = mapped_column(default=100)  # TODO: starting balance for new users?
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="open")  # TODO: what are the valid statuses?
    pool_yes: Mapped[float] = mapped_column(default=100)  # TODO: starting AMM pool size?
    pool_no: Mapped[float] = mapped_column(default=100)
    k: Mapped[float] = mapped_column()  # TODO: how is k derived from pool_yes/pool_no?
    resolve_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Bet(Base):
    __tablename__ = "bets"
    __table_args__ = (CheckConstraint("side IN ('yes', 'no')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    #side represents "yes" or "no", size of 3 to accomodate "yes"
    side: Mapped[str] = mapped_column(String(3))  # TODO: what values? consider a CheckConstraint
    amount: Mapped[float] = mapped_column()
    shares: Mapped[float] = mapped_column()
    price: Mapped[float] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Position(Base):
    __tablename__ = "positions"
    #below makes sure we only have entry of user 1, market_id 1 and side "yes" for example
    __table_args__ = (
        UniqueConstraint("user_id", "market_id", "side"),
        CheckConstraint("side IN ('yes', 'no')"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    side: Mapped[str] = mapped_column(String(3))
    shares: Mapped[float] = mapped_column()
    avg_price: Mapped[float] = mapped_column()
