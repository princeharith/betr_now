from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Bet, Market, Position, User
from app.models.schemas import BetCreate, BetResponse, PositionResponse, UserResponse
from app.services.amm import calculate_shares, get_prices
from app.services.kafka_producer import publish_bet_event
from app.services.redis_service import cache_odds, publish_odds_update

router = APIRouter(tags=["bets"])


@router.post("/bets", response_model=BetResponse)
async def place_bet(payload: BetCreate, db: AsyncSession = Depends(get_db)) -> Bet:
    market = await db.get(Market, payload.market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")
    if market.status != "open":
        raise HTTPException(status_code=400, detail="Market is not open for betting")

    user = await db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.balance < payload.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # 1. Run the AMM math (pure function, no DB/IO involved — see amm.py).
    shares, new_pool_yes, new_pool_no = calculate_shares(
        market.pool_yes, market.pool_no, payload.side, payload.amount
    )

    # 2. Apply the resulting state changes. Mutating `user`/`market` here is
    # enough for SQLAlchemy to pick them up as UPDATEs on flush/commit — no
    # db.add() needed, since both objects were already loaded via db.get()
    # and are tracked by the session.
    user.balance -= payload.amount
    market.pool_yes = new_pool_yes
    market.pool_no = new_pool_no

    # 3. Record the transaction. `price` here is the average price actually
    # paid per share on *this* trade (amount / shares) — not the resulting
    # spot price. This tells you what this specific bet cost, as opposed to
    # what the market looks like after it.
    bet = Bet(
        user_id=payload.user_id,
        market_id=payload.market_id,
        side=payload.side,
        amount=payload.amount,
        shares=shares,
        price=payload.amount / shares,
    )
    db.add(bet)

    # 4. Upsert the Position: one row per (user, market, side) — recall the
    # UniqueConstraint from models.py. If this is the user's first bet on
    # this side of this market, insert a new row; otherwise, fold the new
    # shares into the existing position with a weighted-average price.
    result = await db.execute(
        select(Position).where(
            Position.user_id == payload.user_id,
            Position.market_id == payload.market_id,
            Position.side == payload.side,
        )
    )
    position = result.scalar_one_or_none()

    if position is None:
        position = Position(
            user_id=payload.user_id,
            market_id=payload.market_id,
            side=payload.side,
            shares=shares,
            avg_price=bet.price,
        )
        db.add(position)
    else:
        total_cost = position.avg_price * position.shares + payload.amount
        total_shares = position.shares + shares
        position.avg_price = total_cost / total_shares
        position.shares = total_shares

    # flush() so `bet.id`/`bet.created_at` are populated (DB-generated,
    # same reasoning as create_user in users.py) before we return/publish.
    await db.flush()

    # 5. Notify other systems. NOTE (known simplification, worth knowing):
    # these fire before get_db()'s final commit(). If something later in
    # this same request somehow failed and triggered a rollback, Kafka/Redis
    # would already have "seen" a bet that Postgres ultimately discarded —
    # a classic dual-write inconsistency. For this project for now, nothing
    # risky happens after this point in the function, so it's low-risk, but
    # a fully rigorous system would use something like an outbox pattern to
    # guarantee these only fire after a successful commit.
    await publish_bet_event(
        {
            "bet_id": bet.id,
            "user_id": bet.user_id,
            "market_id": bet.market_id,
            "side": bet.side,
            "amount": bet.amount,
            "shares": bet.shares,
            "price": bet.price,
        }
    )

    yes_price, no_price = get_prices(market.pool_yes, market.pool_no)
    await cache_odds(market.id, yes_price, no_price)
    await publish_odds_update(market.id, yes_price, no_price)

    return bet


@router.get("/positions/{user_id}", response_model=List[PositionResponse])
async def get_positions(user_id: int, db: AsyncSession = Depends(get_db)) -> List[Position]:
    result = await db.execute(select(Position).where(Position.user_id == user_id))
    return list(result.scalars().all())


@router.get("/leaderboard", response_model=List[UserResponse])
async def get_leaderboard(db: AsyncSession = Depends(get_db)) -> List[User]:
    # Simplest possible leaderboard: rank by current cash balance. A more
    # complete version would factor in the value of open positions too —
    # left as-is for now since payout/settlement logic isn't built yet.
    result = await db.execute(select(User).order_by(User.balance.desc()).limit(10))
    return list(result.scalars().all())
