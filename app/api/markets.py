from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Market, Position, User
from app.models.schemas import MarketCreate, MarketResolve, MarketResponse

router = APIRouter(prefix="/markets", tags=["markets"])


@router.post("", response_model=MarketResponse)
async def create_market(payload: MarketCreate, db: AsyncSession = Depends(get_db)) -> Market:
    # The Market model's pool_yes/pool_no columns already default to 100 at
    # the DB level — but we need concrete numbers *here* in Python to compute
    # k, since k has no column default (recall from models.py: it's derived,
    # not independent). So set them explicitly rather than relying on the
    # column default, so both pools and k stay consistent with each other.
    pool_yes = 100  # TODO: what starting value? (hint: match the column default)
    pool_no = 100

    market = Market(
        title=payload.title,
        description=payload.description,
        creator_id=payload.creator_id,
        pool_yes=pool_yes,
        pool_no=pool_no,
        k=pool_yes*pool_no,  # TODO: derive this from pool_yes/pool_no
        resolve_at=payload.resolve_at,
    )
    db.add(market)
    await db.flush()  # TODO: why do we need this? (same reason as create_user in users.py)
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

    return market
