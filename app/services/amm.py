from __future__ import annotations

from typing import Tuple


def calculate_shares(
    pool_yes: float, pool_no: float, side: str, amount: float
) -> Tuple[float, float, float]:
    """Returns (shares_received, new_pool_yes, new_pool_no)."""
    k = pool_yes * pool_no

    if side == "yes":
        new_pool_no = pool_no + amount
        new_pool_yes = k / new_pool_no
        shares = pool_yes - new_pool_yes
        return shares, new_pool_yes, new_pool_no

    elif side == "no":
        new_pool_yes = pool_yes + amount
        new_pool_no = k / new_pool_yes
        shares = pool_no - new_pool_no
        return shares, new_pool_yes, new_pool_no

    else:
        raise ValueError(f"invalid side: {side}")


def get_prices(pool_yes: float, pool_no: float) -> Tuple[float, float]:
    """Returns (yes_price, no_price) — implied probabilities, must sum to 1."""
    yes_price = pool_no / (pool_yes + pool_no)
    no_price = pool_yes / (pool_yes + pool_no)
    return yes_price, no_price
