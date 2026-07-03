from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Market
from app.models.schemas import MarketCreate, MarketResponse

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
async def resolve_market(market_id: int, db: AsyncSession = Depends(get_db)) -> Market:
    # TODO: fetch the market (reuse the lookup pattern above, 404 if missing)
    market = await db.get(Market, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    if market.status == "resolved":
        raise HTTPException(status_code=400, detail="Market already resolved")
   
    market.status = "resolved"
    await db.flush()
    return market   

    # NOTE: actually paying out winning Positions is bigger logic planned for
    # Week 2 (per the roadmap). This endpoint is just a status flip for now —
    # but as flagged above, there's currently no column to record *which side*
    # won, which you'll need before real settlement can work.
