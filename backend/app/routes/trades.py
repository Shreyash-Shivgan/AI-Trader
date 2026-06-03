from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/history")
async def history() -> dict[str, object]:
    return {"trades": []}


@router.get("/open")
async def open_trades() -> dict[str, object]:
    return {"trades": []}
