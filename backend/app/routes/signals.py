from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/live")
async def live_signals() -> dict[str, object]:
    return {"signals": []}
