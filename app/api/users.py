from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import User
from app.models.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    user = User(username=payload.username, display_name=payload.display_name)
    db.add(user)
    # flush() sends the pending INSERT to Postgres *within the current
    # transaction* (not a commit — get_db() still commits/rolls back at the
    # end). We need this now because response_model=UserResponse requires
    # `id` and `created_at`, which only exist after Postgres actually
    # generates them — they're not set on the Python object until this point.
    await db.flush()
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)) -> User:
    # db.get() is a primary-key lookup — SQLAlchemy checks its in-memory
    # identity map first, then falls back to a SELECT if not already loaded.
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db)) -> List[User]:
    # select() is SQLAlchemy 2.0's query-building style. .scalars() unwraps
    # each result row into the actual User object (instead of a 1-tuple).
    result = await db.execute(select(User))
    return list(result.scalars().all())
