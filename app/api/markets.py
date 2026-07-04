from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Market, Position, User
from app.models.schemas import MarketCreate, MarketResolve, MarketResponse
from app.services.redis_service import cache_odds

router = APIRouter(prefix="/markets", tags=["markets"])


@router.post("", response_model=MarketResponse)
async def create_market(payload: MarketCreate, db: AsyncSession = Depends(get_db)) -> Market:
    # The creator is the liquidity provider: their seed money is staked and
    # mints the starting pools ($1 per YES+NO pair, so seed dollars -> a
    # (seed, seed) pool). They get the pool's residual back at resolution —
    # profiting on balanced/wrong crowds, losing when the crowd bets right.
    creator = await db.get(User, payload.creator_id)
    if creator is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    if creator.balance < payload.seed:
        raise HTTPException(
            status_code=400, detail="Insufficient balance to seed market liquidity"
        )
    creator.balance -= payload.seed

    market = Market(
        title=payload.title,
        description=payload.description,
        creator_id=payload.creator_id,
        pool_yes=payload.seed,
        pool_no=payload.seed,
        k=payload.seed * payload.seed,
        resolve_at=payload.resolve_at,
    )
    db.add(market)
    await db.flush()

    # Initialize the Redis odds cache at 50/50. Equal pools are always 50/50,
    # and this overwrites any stale entry left under a recycled market id
    # (e.g. after a dev DB reset that didn't also flush Redis).
    await cache_odds(market.id, 0.5, 0.5)

    return market


@router.get("/{market_id}", response_model=MarketResponse)
async def get_market(market_id: int, db: AsyncSession = Depends(get_db)) -> Market:
    market = await db.get(Market, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


@router.get("", response_model=List[MarketResponse])
async def list_markets(db: AsyncSession = Depends(get_db)) -> List[Market]:
    # TODO: same pattern as list_users — select(Market), .scalars().all()
    result = await db.execute(select(Market))
    return list(result.scalars().all())


@router.post("/{market_id}/resolve", response_model=MarketResponse)
async def resolve_market(
    market_id: int, payload: MarketResolve, db: AsyncSession = Depends(get_db)
) -> Market:
    market = await db.get(Market, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    if market.status == "resolved":
        raise HTTPException(status_code=400, detail="Market already resolved")

    market.status = "resolved"
    market.outcome = payload.outcome

    # Settlement: every winning share pays out exactly $1; losing shares pay
    # $0. Load each Position on the winning side and credit its holder.
    # All of this happens inside the same transaction as the status flip —
    # if any payout failed, get_db() rolls back everything, so the market
    # can never end up "resolved" with winners left unpaid.
    result = await db.execute(
        select(Position).where(
            Position.market_id == market_id,
            Position.side == payload.outcome,
        )
    )
    winning_positions = result.scalars().all()

    for position in winning_positions:
        user = await db.get(User, position.user_id)
        user.balance += position.shares  # shares × $1 per share

    # LP payout: the pool still holds inventory on both sides. The winning
    # side's shares pay $1 each, straight back to the creator who staked the
    # seed; the losing side's are worthless. This is what makes the whole
    # game zero-sum among real players — the "house" P&L lands on the LP.
    creator = await db.get(User, market.creator_id)
    residual = market.pool_yes if payload.outcome == "yes" else market.pool_no
    creator.balance += residual

    return market
