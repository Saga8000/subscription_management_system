"""Money helpers. Rounding policy: ROUND_HALF_UP to 2 decimal places, applied per line."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


def round_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def percent_of(amount: Decimal, percent: Decimal) -> Decimal:
    return round_money(amount * percent / HUNDRED)


def allocate_proportionally(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `total` across `weights` in cents; the rounding remainder goes to the largest weight
    so the parts always sum exactly to `total`."""
    if not weights:
        return []
    weight_sum = sum(weights, ZERO)
    if weight_sum == 0:
        return [ZERO for _ in weights]
    parts = [round_money(total * w / weight_sum) for w in weights]
    remainder = round_money(total) - sum(parts, ZERO)
    if remainder:
        largest = max(range(len(weights)), key=lambda i: weights[i])
        parts[largest] += remainder
    return parts
