from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Market, User
from app.models.schemas import SettlementResponse

router = APIRouter(tags=["settlement"])

STARTING_BALANCE = 100.0
# Ignore sub-cent dust from float math so we don't emit "$0.00" Venmos.
EPSILON = 0.005


@router.get("/settlement", response_model=SettlementResponse)
async def get_settlement(db: AsyncSession = Depends(get_db)) -> dict:
    users = (await db.execute(select(User))).scalars().all()
    open_markets = (
        await db.execute(
            select(func.count()).select_from(Market).where(Market.status == "open")
        )
    ).scalar() or 0

    # Net position vs. the starting stake: + means owed real money, − means owes.
    creditors = []  # [user, amount owed to them]
    debtors = []    # [user, amount they owe]
    for u in users:
        net = u.balance - STARTING_BALANCE
        if net > EPSILON:
            creditors.append([u, net])
        elif net < -EPSILON:
            debtors.append([u, -net])

    total_credit = sum(c[1] for c in creditors)
    total_debt = sum(d[1] for d in debtors)

    # Nets don't sum to zero here: the pool's seed liquidity silently absorbs
    # (or supplies) the imbalance, but "the house" isn't a person who can
    # Venmo anyone. So settle the overlap — min(total won, total lost) — and
    # scale each side pro-rata. Nobody pays more than they lost, nobody
    # receives more than they won.
    pot = min(total_credit, total_debt)
    if pot <= EPSILON:
        return {"payments": [], "open_markets": open_markets}

    for c in creditors:
        c[1] *= pot / total_credit
    for d in debtors:
        d[1] *= pot / total_debt

    # Greedy matching, largest-vs-largest: classic Splitwise-style debt
    # simplification. Produces at most (debtors + creditors - 1) payments.
    creditors.sort(key=lambda c: -c[1])
    debtors.sort(key=lambda d: -d[1])

    payments = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        pay = min(debtors[i][1], creditors[j][1])
        if pay > EPSILON:
            payments.append(
                {
                    "from_username": debtors[i][0].username,
                    "to_username": creditors[j][0].username,
                    "amount": round(pay, 2),
                }
            )
        debtors[i][1] -= pay
        creditors[j][1] -= pay
        if debtors[i][1] <= EPSILON:
            i += 1
        if creditors[j][1] <= EPSILON:
            j += 1

    return {"payments": payments, "open_markets": open_markets}
