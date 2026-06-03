from app.routes.analysis import router as analysis_router
from app.routes.market import router as market_router
from app.routes.performance import router as performance_router
from app.routes.trades import router as trades_router

__all__ = ["analysis_router", "market_router", "performance_router", "trades_router"]
