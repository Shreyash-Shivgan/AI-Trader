from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/summary")
async def summary() -> dict[str, object]:
    return {
        "win_rate": None,
        "average_rr": None,
        "profit_factor": None,
        "drawdown": None,
        "monthly_performance": [],
        "note": "Performance analytics wiring is ready; data aggregation comes from persisted trades and signals.",
    }
