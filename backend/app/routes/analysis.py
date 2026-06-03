from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.analysis_engine import AnalysisEngine
from app.services.market_data import market_data_service

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/{symbol}")
async def analyze_symbol(
    symbol: str,
    timeframe: str = Query(default="5m"),
    account_balance: float = Query(default=10000.0, ge=0.0),
    risk_percent: float = Query(default=1.0, ge=0.01, le=10.0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    engine = AnalysisEngine(db=db, market_data_service=market_data_service)
    try:
        return await engine.analyze_symbol(
            symbol, timeframe, account_balance, risk_percent
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
